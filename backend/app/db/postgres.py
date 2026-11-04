"""PostgreSQL async connection via SQLAlchemy."""

import asyncio
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=settings.SQL_ECHO,
    pool_size=settings.POSTGRES_POOL_SIZE,
    max_overflow=settings.POSTGRES_MAX_OVERFLOW,
    # Test connections before use and recycle them periodically: managed databases
    # (AWS RDS, proxies, firewalls) silently drop idle connections.
    pool_pre_ping=True,
    pool_recycle=settings.POSTGRES_POOL_RECYCLE_SECONDS,
    connect_args=settings.asyncpg_connect_args(),
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def check_connection() -> None:
    """Fail fast with an actionable message if PostgreSQL cannot be reached."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise RuntimeError(
            f"Cannot connect to PostgreSQL ({settings.DATABASE_URL_SAFE}): {type(exc).__name__}: {exc}\n"
            "  - Is the PostgreSQL server running (Windows: services.msc -> postgresql-x64-NN)?\n"
            "  - Do POSTGRES_HOST / PORT / DB / USER / PASSWORD in .env match the role and database you "
            "created in pgAdmin?\n"
            "  - See docs/LOCAL-POSTGRES-PGADMIN.md"
        ) from exc


async def init_db() -> None:
    """Verify the connection, then apply all pending Alembic migrations."""
    await check_connection()

    def upgrade_schema() -> None:
        # postgres.py lives in app/db/ -> backend root is parents[2]
        # (/app/app/db/postgres.py -> /app/alembic.ini in Docker,
        #  backend/app/db/postgres.py -> backend/alembic.ini locally).
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        # Keep the application's logging configuration: alembic.ini's fileConfig() would
        # otherwise silence every application logger after the first migration run.
        config.attributes["configure_logger"] = False
        command.upgrade(config, "head")

    await asyncio.to_thread(upgrade_schema)


async def dispose_engine() -> None:
    await engine.dispose()


async def get_db():
    """FastAPI dependency: yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
