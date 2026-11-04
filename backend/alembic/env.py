"""Alembic environment configuration."""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool, text

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import settings  # noqa: E402
from app.db.postgres import Base  # noqa: E402
from app.models import case, user  # noqa: E402,F401  (register models on Base.metadata)

config = context.config

# When the application runs the migrations itself (app.db.postgres.init_db) it sets
# `configure_logger=False`: fileConfig() would replace the app's logging setup.
# On the command line (`alembic upgrade head`) alembic.ini keeps configuring logging,
# but without disabling loggers that already exist.
if config.config_file_name is not None and config.attributes.get(
    "configure_logger", True
):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# Every process serialises its migrations on this PostgreSQL advisory lock, so
# several containers/workers starting at once cannot race each other.
MIGRATION_LOCK_ID = 727_274_001


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL_SYNC,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # The URL object is used directly (not written into alembic.ini), so passwords
    # containing '%', '@' or '/' neither break configparser interpolation nor the URL.
    connectable = create_engine(settings.database_url_sync, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        # Nothing may be executed on `connection` before configure(): SQLAlchemy 2.0
        # would autobegin a transaction that alembic then treats as external and never commits.
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            if connection.dialect.name == "postgresql":
                connection.execute(
                    text(f"SELECT pg_advisory_xact_lock({MIGRATION_LOCK_ID})")
                )
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
