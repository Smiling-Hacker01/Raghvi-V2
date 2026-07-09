from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()
engine_options = {"pool_pre_ping": True}
if settings.database_url.startswith("postgresql"):
    engine_options.update(
        {
            "pool_size": 5,
            "max_overflow": 10,
            "connect_args": {"timeout": 3},
        }
    )

# Single shared engine, created once at import time. Engine creation is
# lazy/cheap (no connection is opened until first use), so this is safe.
#
# PostgreSQL uses a small pool and a short connect timeout so unreachable
# databases fail fast. SQLite test engines skip those PostgreSQL-only options.
engine: AsyncEngine = create_async_engine(settings.database_url, **engine_options)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
