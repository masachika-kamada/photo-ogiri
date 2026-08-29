import asyncio
import random
import secrets
import string
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import uvicorn
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from photo_ogiri.config import get_settings
from photo_ogiri.database import SessionFactory, engine, get_session
from photo_ogiri.images import normalize_image
from photo_ogiri.jobs import create_scoring_queue
from photo_ogiri.judge import Judge
from photo_ogiri.models import (
    Base,
    Game,
    GameStatus,
    Player,
    Round,
    RoundStatus,
    Submission,
    SubmissionStatus,
)
from photo_ogiri.prompts import choose_prompts
from photo_ogiri.schemas import (
    CreateGameRequest,
    GameCreated,
    GameView,
    JoinGameRequest,
    PlayerJoined,
)
from photo_ogiri.scoring import rank_points
from photo_ogiri.storage import ImageStorage, create_storage

settings = get_settings()
storage: ImageStorage = create_storage(settings)
judge = Judge()
scoring_queue = create_scoring_queue(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as connection:
        if not settings.database_url.startswith("sqlite"):
            await connection.execute(text("SELECT pg_advisory_xact_lock(723608147)"))
        await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="AI審査員フォト大喜利", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bearer token is required")
    return authorization.removeprefix("Bearer ").strip()


def deadline_passed(deadline: datetime) -> bool:
    return datetime.now(timezone.utc) > as_utc(deadline)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def game_by_code(session: AsyncSession, code: str, lock: bool = False) -> Game:
    query = select(Game).where(Game.code == code.upper())
    if lock and not settings.database_url.startswith("sqlite"):
        query = query.with_for_update()
    game = await session.scalar(query)
    if game is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Game not found")
    return game


async def lock_round(session: AsyncSession, round_id: str, shared: bool) -> None:
    if settings.database_url.startswith("sqlite"):
        return
    function = "pg_advisory_xact_lock_shared" if shared else "pg_advisory_xact_lock"
    await session.execute(
        text(f"SELECT {function}(hashtext(:round_id))"), {"round_id": round_id}
    )


async def score_submission(submission_id: str, terminal_failure: bool = True) -> None:
    async with SessionFactory() as session:
        query = (
            select(Submission)
            .where(Submission.id == submission_id)
            .options(selectinload(Submission.round))
        )
        if not settings.database_url.startswith("sqlite"):
            query = query.with_for_update()
        submission = await session.scalar(query)
        if submission is None or submission.status != SubmissionStatus.queued:
            return
        try:
            content = await storage.get(submission.blob_name)
            submission.ai_score = await judge.score(submission.round.prompt, content)
            submission.status = SubmissionStatus.scored
        except Exception:
            await session.rollback()
            if not terminal_failure:
                raise
            submission = await session.get(Submission, submission_id)
            if submission is not None:
                submission.status = SubmissionStatus.failed
        await session.commit()


async def mark_submission_failed(submission_id: str) -> None:
    async with SessionFactory() as session:
        submission = await session.get(Submission, submission_id)
        if submission is not None and submission.status == SubmissionStatus.queued:
            submission.status = SubmissionStatus.failed
            await session.commit()


@app.get("/api/health")
async def health() -> dict[str, str]:
    async with SessionFactory() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/api/games", response_model=GameCreated, status_code=status.HTTP_201_CREATED)
async def create_game(
    request: CreateGameRequest, session: AsyncSession = Depends(get_session)
) -> GameCreated:
    if request.prompt_pack:
        if request.prompts:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Choose a prompt pack or custom prompts",
            )
        prompts = choose_prompts(request.prompt_pack, request.round_count)
    else:
        prompts = [prompt.strip() for prompt in request.prompts if prompt.strip()]
        if not prompts or len(prompts) != len(request.prompts):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Custom prompts must not be blank"
            )

    for _ in range(10):
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if await session.scalar(select(Game.id).where(Game.code == code)) is None:
            break
    else:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Could not allocate a game code"
        )

    game = Game(
        code=code,
        host_token=secrets.token_urlsafe(32),
        title=request.title,
        round_seconds=request.round_seconds,
        max_players=min(request.max_players, settings.max_players),
    )
    game.rounds = [
        Round(number=index, prompt=prompt)
        for index, prompt in enumerate(prompts, start=1)
    ]
    session.add(game)
    await session.commit()
    return GameCreated(code=game.code, host_token=game.host_token)


@app.post(
    "/api/games/{code}/players",
    response_model=PlayerJoined,
    status_code=status.HTTP_201_CREATED,
)
async def join_game(
    code: str, request: JoinGameRequest, session: AsyncSession = Depends(get_session)
) -> PlayerJoined:
    try:
        async with session.begin():
            game = await game_by_code(session, code, lock=True)
            if game.status != GameStatus.lobby:
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "Game has already started"
                )
            player_count = await session.scalar(
                select(func.count(Player.id)).where(Player.game_id == game.id)
            )
            if (player_count or 0) >= game.max_players:
                raise HTTPException(status.HTTP_409_CONFLICT, "Game is full")
            player = Player(
                game_id=game.id,
                name=request.name.strip(),
                token=secrets.token_urlsafe(32),
            )
            session.add(player)
    except IntegrityError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Display name is already in use"
        ) from error
    return PlayerJoined(player_id=player.id, player_token=player.token)


@app.post("/api/games/{code}/advance", status_code=status.HTTP_204_NO_CONTENT)
async def advance_game(
    code: str,
    token: str = Depends(bearer_token),
    session: AsyncSession = Depends(get_session),
) -> Response:
    game = await game_by_code(session, code, lock=True)
    if not secrets.compare_digest(token, game.host_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Host token is invalid")

    rounds = list(
        await session.scalars(
            select(Round).where(Round.game_id == game.id).order_by(Round.number)
        )
    )
    if game.status == GameStatus.lobby:
        game.status = GameStatus.playing
        game.current_round = 1
        rounds[0].status = RoundStatus.active
        rounds[0].deadline = datetime.now(timezone.utc) + timedelta(
            seconds=game.round_seconds
        )
    elif game.status == GameStatus.playing:
        current = rounds[game.current_round - 1]
        if current.status == RoundStatus.scored:
            game.current_round += 1
            following = rounds[game.current_round - 1]
            following.status = RoundStatus.active
            following.deadline = datetime.now(timezone.utc) + timedelta(
                seconds=game.round_seconds
            )
            await session.commit()
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        await lock_round(session, current.id, shared=False)
        await session.refresh(current)
        if current.status == RoundStatus.scored:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Round has already been scored"
            )
        pending = await session.scalar(
            select(func.count(Submission.id)).where(
                Submission.round_id == current.id,
                Submission.status == SubmissionStatus.queued,
            )
        )
        if pending:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "AI scoring is still in progress"
            )
        submissions = list(
            await session.scalars(
                select(Submission)
                .where(Submission.round_id == current.id)
                .options(selectinload(Submission.player))
            )
        )
        ranked = rank_points(
            [
                (item.id, item.ai_score)
                for item in submissions
                if item.ai_score is not None
            ]
        )
        by_id = {item.id: item for item in submissions}
        for submission_id, rank, points in ranked:
            item = by_id[submission_id]
            item.rank = rank
            item.points = points
            item.player.total_points += points
            if rank == 1:
                item.player.wins += 1
        current.status = RoundStatus.scored
        if game.current_round == len(rounds):
            game.status = GameStatus.finished
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/api/games/{code}/submissions", status_code=status.HTTP_202_ACCEPTED)
async def submit_image(
    code: str,
    background_tasks: BackgroundTasks,
    image: UploadFile = File(),
    token: str = Depends(bearer_token),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    game = await game_by_code(session, code)
    player_query = select(Player).where(
        Player.game_id == game.id, Player.token == token
    )
    if not settings.database_url.startswith("sqlite"):
        player_query = player_query.with_for_update()
    player = await session.scalar(player_query)
    if player is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Player token is invalid")
    if game.status != GameStatus.playing:
        raise HTTPException(status.HTTP_409_CONFLICT, "No round is active")
    current = await session.scalar(
        select(Round).where(
            Round.game_id == game.id, Round.number == game.current_round
        )
    )
    if current is not None:
        await lock_round(session, current.id, shared=True)
        await session.refresh(game)
        await session.refresh(current)
    if current is None or current.status != RoundStatus.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "No round is active")
    if current.deadline and deadline_passed(current.deadline):
        raise HTTPException(status.HTTP_409_CONFLICT, "Submission deadline has passed")

    content = await image.read(settings.max_image_bytes + 1)
    if len(content) > settings.max_image_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image is too large"
        )
    try:
        normalized = await asyncio.to_thread(normalize_image, content)
    except Exception as error:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Invalid image"
        ) from error

    existing_query = select(Submission).where(
        Submission.round_id == current.id,
        Submission.player_id == player.id,
    )
    if not settings.database_url.startswith("sqlite"):
        existing_query = existing_query.with_for_update()
    existing = await session.scalar(existing_query)
    blob_name = f"{game.id}/{current.id}/{player.id}.jpg"
    await storage.put(blob_name, normalized)
    if existing:
        existing.status = SubmissionStatus.queued
        existing.ai_score = None
        existing.blob_name = blob_name
        submission = existing
    else:
        submission = Submission(
            round_id=current.id, player_id=player.id, blob_name=blob_name
        )
        session.add(submission)
    await session.commit()
    if scoring_queue:
        await scoring_queue.enqueue(submission.id)
    else:
        background_tasks.add_task(score_submission, submission.id)
    return {"submission_id": submission.id, "status": submission.status.value}


@app.get("/api/games/{code}", response_model=GameView)
async def get_game(code: str, session: AsyncSession = Depends(get_session)) -> GameView:
    game = await session.scalar(
        select(Game)
        .where(Game.code == code.upper())
        .options(
            selectinload(Game.players),
            selectinload(Game.rounds)
            .selectinload(Round.submissions)
            .selectinload(Submission.player),
        )
    )
    if game is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Game not found")
    current = next(
        (item for item in game.rounds if item.number == game.current_round), None
    )
    round_view = None
    if current:
        round_view = {
            "number": current.number,
            "prompt": current.prompt,
            "status": current.status.value,
            "deadline": as_utc(current.deadline) if current.deadline else None,
            "submissions": [
                {
                    "id": item.id,
                    "player_id": item.player_id,
                    "player_name": item.player.name,
                    "image_url": f"/api/images/{item.id}",
                    "status": item.status.value,
                    "ai_score": item.ai_score,
                    "points": item.points,
                    "rank": item.rank,
                }
                for item in sorted(
                    current.submissions, key=lambda entry: entry.rank or 9999
                )
            ],
        }
    players = sorted(
        game.players, key=lambda item: (-item.total_points, -item.wins, item.name)
    )
    return GameView(
        code=game.code,
        title=game.title,
        status=game.status.value,
        current_round=game.current_round,
        round_count=len(game.rounds),
        round_seconds=game.round_seconds,
        max_players=game.max_players,
        players=[
            {
                "id": item.id,
                "name": item.name,
                "total_points": item.total_points,
                "wins": item.wins,
            }
            for item in players
        ],
        round=round_view,
    )


@app.get("/api/images/{submission_id}")
async def get_image(
    submission_id: str, session: AsyncSession = Depends(get_session)
) -> Response:
    submission = await session.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Image not found")
    return Response(await storage.get(submission.blob_name), media_type="image/jpeg")


if settings.frontend_path and settings.frontend_path.is_dir():
    app.mount(
        "/", StaticFiles(directory=settings.frontend_path, html=True), name="frontend"
    )


def main() -> None:
    uvicorn.run("photo_ogiri.api:app", host="0.0.0.0", port=8000, reload=False)
