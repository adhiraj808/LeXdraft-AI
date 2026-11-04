"""Health check endpoints."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.db.postgres import get_db
from app.db.redis_client import get_redis, redis_mode

router = APIRouter()


@router.get("/health/live")
@limiter.exempt
async def liveness():
    """Process is up. Touches no dependency, so a database blip never gets the container killed.

    Use this for container/load-balancer health checks (Docker HEALTHCHECK, AWS ALB target group).
    """
    return {"status": "alive"}


@router.get("/health")
@limiter.exempt
async def health_check(request: Request, db: AsyncSession = Depends(get_db)):
    """Readiness: database + Redis connectivity and NLP pipeline state."""
    redis_ok = False
    try:
        await get_redis().ping()
        redis_ok = True
    except Exception:
        pass

    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    pipeline = getattr(request.app.state, "nlp_pipeline", None)
    nlp_loaded = bool(pipeline is not None and pipeline._loaded)

    mode = redis_mode()
    if not redis_ok:
        redis_state = "disconnected"
    else:
        # "memory" = running on the in-process fallback because no Redis server is configured/reachable.
        redis_state = "in-memory" if mode == "memory" else "connected"

    return {
        "status": "ok" if (redis_ok and db_ok) else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "redis": redis_state,
        "nlp_pipeline": "loaded" if nlp_loaded else "not_loaded",
    }
