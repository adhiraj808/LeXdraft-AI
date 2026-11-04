"""Redis async client for case caching, draft storage and progress pub/sub.

Everything cached here is also stored in PostgreSQL, so Redis is an optimisation and
never a source of truth. That is why:

* when Redis is unreachable the app transparently switches to a small in-process
  store (``InMemoryRedis``) unless ``REDIS_REQUIRED=true``;
* every high-level helper below is best-effort: a cache failure is logged and
  swallowed instead of failing the request (or marking a finished case as failed).
"""

import asyncio
import json
import logging
import time
from collections import OrderedDict
from functools import wraps
from inspect import isawaitable
from typing import Any, Dict, List, Optional, Tuple

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── In-process fallback ──────────────────────────────────────────────────────


class _Entry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, expires_at: Optional[float] = None) -> None:
        self.value = value
        self.expires_at = expires_at


class _InMemoryPipeline:
    """Queues commands and runs them on ``execute()`` (same shape as redis-py's pipeline)."""

    def __init__(self, store: "InMemoryRedis") -> None:
        self._store = store
        self._ops: List[Tuple[str, tuple, dict]] = []

    async def __aenter__(self) -> "_InMemoryPipeline":
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        self._ops.clear()

    # `async def` on purpose: callers write `await pipe.hset(...)`.
    async def hset(self, *args: Any, **kwargs: Any) -> "_InMemoryPipeline":
        self._ops.append(("hset", args, kwargs))
        return self

    async def expire(self, *args: Any, **kwargs: Any) -> "_InMemoryPipeline":
        self._ops.append(("expire", args, kwargs))
        return self

    async def set(self, *args: Any, **kwargs: Any) -> "_InMemoryPipeline":
        self._ops.append(("set", args, kwargs))
        return self

    async def delete(self, *args: Any, **kwargs: Any) -> "_InMemoryPipeline":
        self._ops.append(("delete", args, kwargs))
        return self

    async def execute(self) -> List[Any]:
        results = [
            await getattr(self._store, name)(*args, **kwargs)
            for name, args, kwargs in self._ops
        ]
        self._ops.clear()
        return results


class _InMemoryPubSub:
    def __init__(self, store: "InMemoryRedis") -> None:
        self._store = store
        self._queue: "asyncio.Queue[Tuple[str, str]]" = asyncio.Queue(maxsize=100)
        self._channels: set = set()

    async def subscribe(self, *channels: str) -> None:
        for channel in channels:
            self._store._channels.setdefault(channel, []).append(self._queue)
            self._channels.add(channel)

    async def unsubscribe(self, *channels: str) -> None:
        for channel in channels or tuple(self._channels):
            queues = self._store._channels.get(channel, [])
            if self._queue in queues:
                queues.remove(self._queue)
            if not queues:
                self._store._channels.pop(channel, None)
            self._channels.discard(channel)

    async def get_message(
        self, ignore_subscribe_messages: bool = False, timeout: float = 0.0
    ) -> Optional[dict]:
        try:
            if timeout:
                channel, data = await asyncio.wait_for(
                    self._queue.get(), timeout=timeout
                )
            else:
                channel, data = self._queue.get_nowait()
        except (asyncio.TimeoutError, asyncio.QueueEmpty):
            return None
        return {"type": "message", "channel": channel, "data": data}

    async def aclose(self) -> None:
        await self.unsubscribe()

    close = aclose


class InMemoryRedis:
    """Tiny in-process stand-in for ``redis.asyncio.Redis``.

    Implements only the commands this application uses. Keys honour their TTL and
    the store is capped at ``max_keys`` (oldest key evicted first), so it cannot grow
    without bound. It is per-process: with several workers each one has its own copy,
    which is fine for a cache of data that also lives in PostgreSQL.
    """

    def __init__(self, max_keys: int = 500) -> None:
        self._data: "OrderedDict[str, _Entry]" = OrderedDict()
        self._max_keys = max(1, max_keys)
        self._channels: Dict[str, List[asyncio.Queue]] = {}

    # -- housekeeping --------------------------------------------------------
    @staticmethod
    def _now() -> float:
        return time.monotonic()

    def _entry(self, key: str) -> Optional[_Entry]:
        entry = self._data.get(key)
        if (
            entry is not None
            and entry.expires_at is not None
            and entry.expires_at <= self._now()
        ):
            del self._data[key]
            return None
        return entry

    def _store_entry(self, key: str, value: Any, ttl: Optional[int] = None) -> _Entry:
        entry = _Entry(value, self._now() + ttl if ttl else None)
        self._data[key] = entry
        self._data.move_to_end(key)
        self._evict()
        return entry

    def _evict(self) -> None:
        if len(self._data) <= self._max_keys:
            return
        now = self._now()
        for key in [
            k
            for k, e in self._data.items()
            if e.expires_at is not None and e.expires_at <= now
        ]:
            del self._data[key]
        while len(self._data) > self._max_keys:
            self._data.popitem(last=False)

    # -- commands ------------------------------------------------------------
    async def ping(self) -> bool:
        return True

    async def hset(
        self,
        name: str,
        key: Any = None,
        value: Any = None,
        mapping: Optional[dict] = None,
    ) -> int:
        entry = self._entry(name)
        if entry is None or not isinstance(entry.value, dict):
            entry = self._store_entry(name, {})
        items = dict(mapping or {})
        if key is not None:
            items[key] = value
        added = sum(1 for field in items if str(field) not in entry.value)
        for field, field_value in items.items():
            entry.value[str(field)] = str(field_value)
        self._data.move_to_end(name)
        return added

    async def hgetall(self, name: str) -> Dict[str, str]:
        entry = self._entry(name)
        return (
            dict(entry.value)
            if entry is not None and isinstance(entry.value, dict)
            else {}
        )

    async def expire(self, name: str, seconds: int) -> bool:
        entry = self._entry(name)
        if entry is None:
            return False
        entry.expires_at = self._now() + seconds
        return True

    async def set(self, name: str, value: Any, ex: Optional[int] = None) -> bool:
        self._store_entry(name, str(value), ex)
        return True

    async def get(self, name: str) -> Optional[str]:
        entry = self._entry(name)
        return (
            entry.value if entry is not None and isinstance(entry.value, str) else None
        )

    async def delete(self, *names: str) -> int:
        return sum(1 for name in names if self._data.pop(name, None) is not None)

    async def publish(self, channel: str, message: str) -> int:
        queues = list(self._channels.get(channel, []))
        for queue in queues:
            try:
                queue.put_nowait((channel, message))
            except asyncio.QueueFull:
                pass  # a stalled subscriber must not block or grow memory
        return len(queues)

    def pubsub(self) -> _InMemoryPubSub:
        return _InMemoryPubSub(self)

    def pipeline(self, transaction: bool = True) -> _InMemoryPipeline:
        return _InMemoryPipeline(self)

    async def aclose(self) -> None:
        self._data.clear()
        self._channels.clear()

    close = aclose


# ── Connection management ────────────────────────────────────────────────────

_redis: Optional[Any] = None  # aioredis.Redis or InMemoryRedis


async def _close_client(client: Any) -> None:
    closer = getattr(client, "aclose", None) or getattr(client, "close", None)
    if closer is None:
        return
    try:
        result = closer()
        if isawaitable(result):
            await result
    except Exception as exc:  # closing must never raise
        logger.debug("Error while closing Redis client: %s", exc)


async def init_redis() -> None:
    """Connect to Redis, or fall back to the in-process store (see module docstring)."""
    global _redis

    if _redis is not None:
        try:
            await _redis.ping()
            return
        except Exception:
            logger.warning("Redis connection lost; reconnecting...")
            _redis = None

    if not settings.REDIS_ENABLED:
        _redis = InMemoryRedis(settings.REDIS_FALLBACK_MAX_KEYS)
        logger.info("Redis disabled (REDIS_ENABLED=false): using the in-process cache.")
        return

    client = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=settings.REDIS_MAX_CONNECTIONS,
        socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
        health_check_interval=30,
    )
    try:
        await asyncio.wait_for(
            client.ping(), timeout=settings.REDIS_CONNECT_TIMEOUT + 1
        )
    except Exception as exc:
        await _close_client(client)
        target = f"{settings.REDIS_HOST}:{settings.REDIS_PORT}"
        if settings.REDIS_REQUIRED:
            raise RuntimeError(
                f"Redis is required (REDIS_REQUIRED=true) but unreachable at {target}: {exc}"
            ) from exc
        logger.warning(
            "Redis unreachable at %s (%s: %s). Continuing with an in-process cache - "
            "set REDIS_ENABLED=false to silence this, or start Redis.",
            target,
            type(exc).__name__,
            exc,
        )
        _redis = InMemoryRedis(settings.REDIS_FALLBACK_MAX_KEYS)
        return

    _redis = client
    logger.info(
        "Redis connected at %s:%s (max_connections=%s).",
        settings.REDIS_HOST,
        settings.REDIS_PORT,
        settings.REDIS_MAX_CONNECTIONS,
    )


async def close_redis() -> None:
    global _redis
    client, _redis = _redis, None
    if client is not None:
        await _close_client(client)


def get_redis() -> Any:
    if _redis is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis


def redis_mode() -> str:
    """'redis' (real server), 'memory' (in-process fallback) or 'unavailable'."""
    if _redis is None:
        return "unavailable"
    return "memory" if isinstance(_redis, InMemoryRedis) else "redis"


async def _client() -> Any:
    if _redis is None:
        await init_redis()
    return get_redis()


def _best_effort(default: Any = None):
    """Log and swallow cache failures: the database stays the source of truth."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                logger.warning(
                    "Redis operation %s failed, continuing without cache: %s",
                    func.__name__,
                    exc,
                )
                return default

        return wrapper

    return decorator


# ── Key helpers ──────────────────────────────────────────────────────────────


def _case_key(case_id: str) -> str:
    return f"case:{case_id}"


def _session_key(session_id: str) -> str:
    return f"session:{session_id}"


def _draft_key(case_id: str) -> str:
    return f"draft:{case_id}"


# ── High-level cache operations ──────────────────────────────────────────────


@_best_effort()
async def cache_case_data(case_id: str, data: dict, ttl: int = None) -> None:
    """Store complete case processing data in Redis."""
    r = await _client()
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


@_best_effort()
async def get_case_data(case_id: str) -> Optional[dict]:
    """Retrieve case data from Redis."""
    r = await _client()
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


@_best_effort()
async def cache_draft(case_id: str, draft: dict, ttl: int = None) -> None:
    """Cache the generated draft sections."""
    r = await _client()
    ttl = ttl or settings.REDIS_TTL_SECONDS
    await r.set(_draft_key(case_id), json.dumps(draft), ex=ttl)


@_best_effort()
async def get_draft(case_id: str) -> Optional[dict]:
    """Retrieve cached draft."""
    r = await _client()
    raw = await r.get(_draft_key(case_id))
    return json.loads(raw) if raw else None


@_best_effort()
async def update_case_status(case_id: str, status: str) -> None:
    """Update the processing status of a case.

    The TTL is refreshed together with the write: a bare HSET on an expired key would
    re-create it *without* an expiry and leak memory in Redis forever.
    """
    r = await _client()
    key = _case_key(case_id)
    async with r.pipeline(transaction=True) as pipe:
        await pipe.hset(key, "status", status)
        await pipe.expire(key, settings.REDIS_TTL_SECONDS)
        await pipe.execute()


@_best_effort()
async def delete_case_cache(case_id: str) -> None:
    """Remove all cached data for a case."""
    r = await _client()
    await r.delete(_case_key(case_id), _draft_key(case_id))


@_best_effort()
async def publish_progress(case_id: str, message: str) -> None:
    """Publish processing progress for SSE streaming."""
    r = await _client()
    await r.publish(f"progress:{case_id}", message)
