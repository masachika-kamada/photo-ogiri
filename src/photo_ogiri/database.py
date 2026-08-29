from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from photo_ogiri.config import get_settings

settings = get_settings()
database_url = make_url(settings.database_url)
if database_url.get_backend_name() == "sqlite" and database_url.database not in (
    None,
    ":memory:",
):
    Path(database_url.database).parent.mkdir(parents=True, exist_ok=True)
engine_options: dict[str, object] = {"pool_pre_ping": True}
if not settings.database_url.startswith("sqlite"):
    engine_options.update(pool_size=5, max_overflow=0, pool_timeout=30)
engine = create_async_engine(settings.database_url, **engine_options)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
