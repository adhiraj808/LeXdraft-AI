"""Redis async client for session caching and draft storage."""

import json
import logging
from typing import Optional, Any
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None


async def init_redis():
    global _redis
    if _redis is not None:
        try:
            await _redis.ping()
            return
        except Exception:
            pass
    _redis = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=settings.REDIS_MAX_CONNECTIONS,
    )
    await _redis.ping()
    logger.info(f"Redis initialized with max_connections={settings.REDIS_MAX_CONNECTIONS}.")


async def close_redis():
    global _redis
    if _redis:
        await _redis.close()


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        # Auto-initialize if not already done
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Can't run async init in sync context, raise error
                raise RuntimeError("Redis not initialized. Call init_redis() first.")
        except RuntimeError:
            pass
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis


# ── Key helpers ──────────────────────────────────────────────────────────────

def _case_key(case_id: str) -> str:
    return f"case:{case_id}"

def _session_key(session_id: str) -> str:
    return f"session:{session_id}"

def _draft_key(case_id: str) -> str:
    return f"draft:{case_id}"


# ── High-level cache operations ───────────────────────────────────────────────

async def cache_case_data(case_id: str, data: dict, ttl: int = None) -> None:
    """Store complete case processing data in Redis."""
    import app.db.redis_client as redis_client
    from app.db.redis_client import init_redis, get_redis
    # Ensure Redis is initialized
    if redis_client._redis is None:
        await init_redis()
    r = get_redis()
    ttl = ttl or settings.REDIS_TTL_SECONDS
    key = _case_key(case_id)
    mapping = {
        k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
        for k, v in data.items()
    }
    async with r.pipeline(transaction=True) as pipe:
        await pipe.hset(key, mapping=mapping)
        await pipe.expire(key, ttl)
        await pipe.execute()


async def get_case_data(case_id: str) -> Optional[dict]:
    """Retrieve case data from Redis."""
    r = get_redis()
    data = await r.hgetall(_case_key(case_id))
    if not data:
        return None
    result = {}
    for k, v in data.items():
        try:
            result[k] = json.loads(v)
        except (json.JSONDecodeError, ValueError):
            result[k] = v
    return result


async def cache_draft(case_id: str, draft: dict, ttl: int = None) -> None:
    """Cache the generated draft sections."""
    r = get_redis()
    ttl = ttl or settings.REDIS_TTL_SECONDS
    await r.set(_draft_key(case_id), json.dumps(draft), ex=ttl)


async def get_draft(case_id: str) -> Optional[dict]:
    """Retrieve cached draft."""
    r = get_redis()
    raw = await r.get(_draft_key(case_id))
    return json.loads(raw) if raw else None


async def update_case_status(case_id: str, status: str) -> None:
    """Update the processing status of a case."""
    r = get_redis()
    await r.hset(_case_key(case_id), "status", status)


async def delete_case_cache(case_id: str) -> None:
    """Remove all cached data for a case."""
    r = get_redis()
    await r.delete(_case_key(case_id), _draft_key(case_id))


async def publish_progress(case_id: str, message: str) -> None:
    """Publish processing progress for SSE streaming."""
    r = get_redis()
    await r.publish(f"progress:{case_id}", message)
