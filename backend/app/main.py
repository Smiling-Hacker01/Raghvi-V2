from fastapi import FastAPI

from app.api.health import router as health_router

app = FastAPI(
    title="Raghvi Backend",
    version="0.1.0",
)

app.include_router(health_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "raghvi-backend", "status": "running"}