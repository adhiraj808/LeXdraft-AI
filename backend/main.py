"""
AI-Powered Legal Case Drafting System
FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.postgres import init_db
from app.db.redis_client import init_redis
from app.nlp.pipeline import NLPPipeline
from app.api.routes import auth, cases, health, rag

logger = logging.getLogger(__name__)

# Global NLP pipeline instance (loaded once at startup)
nlp_pipeline: NLPPipeline = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""
    global nlp_pipeline

    setup_logging()
    logger.info("Starting Legal Draft AI System...")

    if not settings.DEBUG and settings.SECRET_KEY == "dev-secret-key-change-in-production":
        raise RuntimeError(
            "SECRET_KEY is still set to the development default. "
            "Set a real random SECRET_KEY in .env before running with DEBUG=false."
        )

    # Initialize database
    await init_db()
    logger.info("PostgreSQL connected.")

    # Initialize Redis
    await init_redis()
    logger.info("Redis connected.")

    # Load NLP models (this may take 30-60s on first run)
    logger.info("Loading NLP models...")
    nlp_pipeline = NLPPipeline()
    await nlp_pipeline.load()
    app.state.nlp_pipeline = nlp_pipeline
    logger.info("NLP pipeline ready.")

    yield

    # Shutdown
    logger.info("Shutting down...")
    from app.db.redis_client import close_redis
    await close_redis()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI-Powered Legal Case Drafting System API",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(cases.router, prefix="/api/v1/cases", tags=["cases"])
    app.include_router(rag.router, prefix="/api/v1/rag", tags=["rag"])

    return app


app = create_app()
