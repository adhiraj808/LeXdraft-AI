"""Pytest configuration and shared fixtures."""

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from unittest.mock import AsyncMock, MagicMock

from app.db.postgres import Base, get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models import case  # noqa: F401 - must be imported so Base.metadata knows about Case/Draft
import uuid

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_engine):
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
def mock_user():
    return User(
        id=str(uuid.uuid4()),
        email="test@example.com",
        username="testuser",
        hashed_password="hashed",
        full_name="Test User",
        role="advocate",
        is_active=True,
    )


@pytest.fixture
async def client(test_engine, db_session, mock_user):
    from main import app
    from app.db import redis_client

    # Mock Redis (no real Redis server in the test environment)
    mock_redis = MagicMock()
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.hset = AsyncMock(return_value=None)
    mock_redis.expire = AsyncMock(return_value=None)
    mock_pipeline = MagicMock()
    mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
    mock_pipeline.__aexit__ = AsyncMock(return_value=None)
    mock_pipeline.hset = AsyncMock(return_value=None)
    mock_pipeline.expire = AsyncMock(return_value=None)
    mock_pipeline.execute = AsyncMock(return_value=[])
    mock_redis.pipeline.return_value = mock_pipeline
    mock_redis.hgetall = AsyncMock(return_value={})
    mock_redis.set = AsyncMock(return_value=None)
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.delete = AsyncMock(return_value=None)
    mock_redis.publish = AsyncMock(return_value=None)
    redis_client._redis = mock_redis

    # Mock NLP pipeline (generator.model_label must be a plain string: process_case
    # stores it in the Draft.model_used column)
    mock_nlp_pipeline = MagicMock()
    mock_nlp_pipeline._loaded = True
    mock_nlp_pipeline.generator.model_label = "test-mock"
    mock_nlp_pipeline.process = AsyncMock(return_value={
        "preprocessed": {"cleaned": "test", "sentences": [], "tokens": [], "legal_sections": [], "word_count": 5, "sentence_count": 1},
        "entities": {"persons": [], "organizations": [], "dates": [], "statutes": [], "courts": [], "locations": [], "money": []},
        "classification": {"case_type": "Criminal", "confidence": 0.9, "probabilities": {}, "method": "keyword"},
        "context": {},
        "draft_sections": {"title_block": "TITLE", "complaint_body": "BODY", "prayer": "PRAYER", "list_of_witnesses": "W", "list_of_documents": "D", "affidavit": "A", "evidence_affidavit": "E", "_generation_time": 1.0, "_full_text": "FULL"},
    })
    app.state.nlp_pipeline = mock_nlp_pipeline

    # Make background draft tasks share the test database instead of the real one.
    import app.db.postgres as postgres_module
    _real_session_factory = postgres_module.AsyncSessionLocal
    postgres_module.AsyncSessionLocal = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: mock_user

    # "localhost" is whitelisted by HostGuardMiddleware (see ALLOWED_HOSTS).
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        yield ac

    postgres_module.AsyncSessionLocal = _real_session_factory
    app.dependency_overrides.clear()
