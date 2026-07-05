import logging

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/ready")
async def ready(response: Response) -> dict[str, str]:
    """Readiness check.

    Verifies the backend can actually reach PostgreSQL by executing a
    real query, not just that the process is alive (see /health for that).
    Returns 503 if the database is unreachable, so callers can distinguish
    "process up" from "process up and able to serve requests".
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Readiness check failed: could not reach PostgreSQL")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable"}
    return {"status": "ok"}