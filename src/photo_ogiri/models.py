import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class GameStatus(str, enum.Enum):
    lobby = "lobby"
    playing = "playing"
    finished = "finished"


class RoundStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    scored = "scored"


class SubmissionStatus(str, enum.Enum):
    queued = "queued"
    scored = "scored"
    failed = "failed"


class Game(Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(6), unique=True, index=True)
    host_token: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(80))
    round_seconds: Mapped[int] = mapped_column(Integer)
    max_players: Mapped[int] = mapped_column(Integer)
    status: Mapped[GameStatus] = mapped_column(Enum(GameStatus), default=GameStatus.lobby)
    current_round: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    rounds: Mapped[list["Round"]] = relationship(back_populates="game", cascade="all, delete-orphan")
    players: Mapped[list["Player"]] = relationship(back_populates="game", cascade="all, delete-orphan")


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("game_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(30))
    token: Mapped[str] = mapped_column(String(64), unique=True)
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)

    game: Mapped[Game] = relationship(back_populates="players")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="player")


class Round(Base):
    __tablename__ = "rounds"
    __table_args__ = (UniqueConstraint("game_id", "number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    prompt: Mapped[str] = mapped_column(String(200))
    status: Mapped[RoundStatus] = mapped_column(Enum(RoundStatus), default=RoundStatus.pending)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    prompt_embedding: Mapped[bytes | None] = mapped_column(LargeBinary)

    game: Mapped[Game] = relationship(back_populates="rounds")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="round", cascade="all, delete-orphan")


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("round_id", "player_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    round_id: Mapped[str] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"), index=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    blob_name: Mapped[str] = mapped_column(String(300), unique=True)
    status: Mapped[SubmissionStatus] = mapped_column(Enum(SubmissionStatus), default=SubmissionStatus.queued)
    ai_score: Mapped[float | None] = mapped_column(Float)
    points: Mapped[int] = mapped_column(Integer, default=0)
    rank: Mapped[int | None] = mapped_column(Integer)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    round: Mapped[Round] = relationship(back_populates="submissions")
    player: Mapped[Player] = relationship(back_populates="submissions")