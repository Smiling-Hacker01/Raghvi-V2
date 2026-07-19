from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.ready import router as ready_router

app = FastAPI(
    title="Raghvi Backend",
    version="0.1.0",
    description="Personal AI assistant backend",
)

# Include all routers
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(health_router)
app.include_router(ready_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "raghvi-backend", "status": "running"}
