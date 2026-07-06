from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness check.

    Confirms the process is running and able to respond to requests.
    Deliberately checks no external dependencies (database, etc.) —
    see /ready for dependency-aware readiness checks.
    """
    return {"status": "ok"}
