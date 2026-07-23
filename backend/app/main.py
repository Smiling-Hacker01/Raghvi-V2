from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.creator import router as creator_router
from app.api.health import router as health_router
from app.api.memories import router as memories_router
from app.api.ready import router as ready_router
from app.services.creator_seed import ensure_creator_seeded_on_startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for FastAPI app."""
    # Automatic creator profile seeding on startup across any environment
    await ensure_creator_seeded_on_startup()
    yield


app = FastAPI(
    title="Raghvi Backend",
    version="0.1.0",
    description="Personal AI assistant backend with chat, memories, and tasks",
    lifespan=lifespan,
)

# Include all routers
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(memories_router)
app.include_router(health_router)
app.include_router(ready_router)
app.include_router(creator_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"service": "raghvi-backend", "status": "running"}
