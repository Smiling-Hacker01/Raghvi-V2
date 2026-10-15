import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.actions import router as actions_router
from app.api.auth import router as auth_router
from app.api.briefings import router as briefings_router
from app.api.chat import router as chat_router
from app.api.communications import router as communications_router
from app.api.connected_accounts import router as connected_accounts_router
from app.api.creator import router as creator_router
from app.api.health import router as health_router
from app.api.meetings import router as meetings_router
from app.api.memories import router as memories_router
from app.api.ready import router as ready_router
from app.api.subscriptions import router as subscriptions_router
from app.api.tasks import router as tasks_router
from app.api.users import router as users_router
from app.api.voices import router as voices_router
from app.api.webhooks import router as webhooks_router
from app.services.creator_seed import ensure_creator_seeded_on_startup

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for FastAPI app."""
    # Ensure all DB tables exist on startup
    import app.models  # noqa: F401
    from app.db.base import Base
    from app.db.session import engine

    retries = 10
    while retries > 0:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            break
        except Exception as e:
            retries -= 1
            if retries == 0:
                logger.error(f"Failed to connect to database on startup after retries: {e}")
                raise
            logger.warning(
                f"Database not ready on startup ({e}). Retrying in 2s ({retries} left)..."
            )
            await asyncio.sleep(2)

    # Automatic creator profile seeding on startup across any environment
    await ensure_creator_seeded_on_startup()
    yield


app = FastAPI(
    title="Raghvi Backend",
    version="0.1.0",
    description="Personal AI assistant backend with chat, memories, and tasks",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(auth_router)
app.include_router(actions_router)
app.include_router(briefings_router)
app.include_router(chat_router)
app.include_router(communications_router)
app.include_router(connected_accounts_router)
app.include_router(memories_router)
app.include_router(health_router)
app.include_router(ready_router)
app.include_router(creator_router)
app.include_router(meetings_router)
app.include_router(tasks_router)
app.include_router(users_router)
app.include_router(subscriptions_router)
app.include_router(voices_router)
app.include_router(webhooks_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"service": "raghvi-backend", "status": "running"}


@app.get("/connected-account-presets", tags=["connected-accounts"], include_in_schema=False)
@app.get("/connected-accounts-presets", tags=["connected-accounts"], include_in_schema=False)
async def get_provider_presets_alias():
    """Alias for /connected-accounts/presets to support both path conventions."""
    from app.services.connected_account_service import ConnectedAccountService

    return ConnectedAccountService.get_presets()
