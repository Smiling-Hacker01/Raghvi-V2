from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.creator import router as creator_router
from app.api.health import router as health_router
from app.api.memories import router as memories_router
from app.api.ready import router as ready_router
from app.api.subscriptions import router as subscriptions_router
from app.api.tasks import router as tasks_router
from app.api.voices import router as voices_router
from app.api.webhooks import router as webhooks_router
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
app.include_router(chat_router)
app.include_router(memories_router)
app.include_router(health_router)
app.include_router(ready_router)
app.include_router(creator_router)
app.include_router(tasks_router)
app.include_router(subscriptions_router)
app.include_router(voices_router)
app.include_router(webhooks_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"service": "raghvi-backend", "status": "running"}
