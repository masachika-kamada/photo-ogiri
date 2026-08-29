from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CreateGameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    prompts: list[str] = Field(default_factory=list, max_length=20)
    prompt_pack: Literal["daily", "discovery", "chaos"] | None = None
    round_count: int = Field(default=3, ge=1, le=10)
    round_seconds: int = Field(default=90, ge=30, le=300)
    max_players: int = Field(default=100, ge=2, le=100)


class JoinGameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=30)


class GameCreated(BaseModel):
    code: str
    host_token: str


class PlayerJoined(BaseModel):
    player_id: str
    player_token: str


class PlayerView(BaseModel):
    id: str
    name: str
    total_points: int
    wins: int


class SubmissionView(BaseModel):
    id: str
    player_id: str
    player_name: str
    image_url: str
    status: str
    ai_score: float | None
    points: int
    rank: int | None


class RoundView(BaseModel):
    number: int
    prompt: str
    status: str
    deadline: datetime | None
    submissions: list[SubmissionView]


class GameView(BaseModel):
    code: str
    title: str
    status: str
    current_round: int
    round_count: int
    round_seconds: int
    max_players: int
    players: list[PlayerView]
    round: RoundView | None
