"""Health check endpoint."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres import get_db
from app.db.redis_client import get_redis

router = APIRouter()


@router.get("/health")
async def health_check(request: Request, db: AsyncSession = Depends(get_db)):
    """Returns system health status, including DB and Redis connectivity (used by the Docker healthcheck)."""
    redis_ok = False
    try:
        r = get_redis()
        await r.ping()
        redis_ok = True
    except Exception:
        pass

    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    nlp_loaded = hasattr(request.app.state, "nlp_pipeline") and request.app.state.nlp_pipeline._loaded

    return {
        "status": "ok" if (redis_ok and db_ok) else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "redis": "connected" if redis_ok else "disconnected",
        "nlp_pipeline": "loaded" if nlp_loaded else "not_loaded",
    }
