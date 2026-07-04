from fastapi import FastAPI

app = FastAPI(
    title="Raghvi Backend",
    version="0.1.0",
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "raghvi-backend", "status": "running"}