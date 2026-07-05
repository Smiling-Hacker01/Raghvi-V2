from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import get_settings

settings = get_settings()

# Single shared engine, created once at import time. Engine creation is
# lazy/cheap (no connection is opened until first use), so this is safe.
#
# pool_pre_ping=True: test a pooled connection before handing it out, so a
# connection that died silently (network blip, DB restart) is detected and
# replaced instead of surfacing as a confusing failure later.
#
# connect_args timeout: fail fast (3s) if PostgreSQL is unreachable, instead
# of hanging on a default OS-level TCP timeout.
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={"timeout": 3},
)