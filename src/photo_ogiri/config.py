from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./data/photo-ogiri.db"
    storage_backend: str = "local"
    local_storage_path: Path = Path("data/uploads")
    frontend_path: Path | None = None
    azure_storage_account_url: str | None = None
    azure_queue_account_url: str | None = None
    azure_storage_connection_string: str | None = None
    azure_blob_container: str = "submissions"
    azure_queue_name: str = "score-jobs"
    azure_poison_queue_name: str = "score-jobs-poison"
    scoring_backend: str = "inline"
    worker_poll_seconds: float = 1.0
    worker_visibility_timeout: int = 300
    worker_max_dequeue_count: int = 5
    max_players: int = 100
    max_image_bytes: int = 8 * 1024 * 1024
    cors_origins: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="PHOTO_OGIRI_")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()