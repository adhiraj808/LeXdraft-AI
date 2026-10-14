"""Unit tests for Redis cache operations."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db import redis_client


@pytest.mark.asyncio
async def test_cache_case_data_batches_write_and_expiry():
    redis = MagicMock()
    pipeline = MagicMock()
    pipeline.__aenter__ = AsyncMock(return_value=pipeline)
    pipeline.__aexit__ = AsyncMock(return_value=None)
    pipeline.hset = AsyncMock()
    pipeline.expire = AsyncMock()
    pipeline.execute = AsyncMock()
    redis.pipeline.return_value = pipeline
    redis_client._redis = redis

    await redis_client.cache_case_data(
        "case-1",
        {"title": "Test", "entities": {"persons": ["A"]}},
        ttl=300,
    )

    redis.pipeline.assert_called_once_with(transaction=True)
    pipeline.hset.assert_awaited_once_with(
        "case:case-1",
        mapping={"title": "Test", "entities": '{"persons": ["A"]}'},
    )
    pipeline.expire.assert_awaited_once_with("case:case-1", 300)
    pipeline.execute.assert_awaited_once()
    redis.hset.assert_not_called()
    redis.expire.assert_not_called()
