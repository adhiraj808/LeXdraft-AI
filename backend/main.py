"""
AI-Powered Legal Case Drafting System
FastAPI Application Entry Point
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import admin, auth, cases, fir_analysis, health, rag
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import (
    BodySizeLimitMiddleware,
    HostGuardMiddleware,
    RequestContextMiddleware,
)
from app.core.rate_limit import limiter
from app.db.postgres import dispose_engine, init_db
from app.db.redis_client import close_redis, init_redis
from app.nlp.pipeline import NLPPipeline
from app.services.case_service import recover_stale_cases

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""
    setup_logging()
    logger.info("Starting Legal Draft AI System...")

    # Refuse to boot with a default/weak JWT signing key outside debug mode.
    settings.assert_secure_for_runtime()

    # Initialize database
    logger.info("About to init_db...")
    await init_db()
    logger.info("PostgreSQL connected.")

    # Mark cases orphaned by a previous process as failed (on 1 worker this is exact;
    # with multiple workers the age gate in recover_stale_cases protects live cases).
    try:
        await recover_stale_cases()
    except Exception:
        logger.exception("Stale-case recovery failed; continuing startup.")

    # Initialize Redis
    logger.info("Initializing Redis...")
    try:
        await init_redis()
        logger.info("Redis connected.")
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {e}")
        raise

    # Load NLP models in background (don't block startup)
    logger.info("Starting NLP model loading in background...")
    nlp_pipeline = NLPPipeline()
    # Start loading in background, don't block startup
    asyncio.create_task(nlp_pipeline.load())
    app.state.nlp_pipeline = nlp_pipeline
    logger.info("NLP pipeline loading started in background.")

    logger.info("Lifespan startup complete, yielding...")

    yield

    # Shutdown
    logger.info("Shutting down...")
    await close_redis()
    await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI-Powered Legal Case Drafting System API",
        docs_url="/docs" if settings.DOCS_ENABLED else None,
        redoc_url="/redoc" if settings.DOCS_ENABLED else None,
        lifespan=lifespan,
    )

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # Security / hygiene middlewares (pure ASGI, no per-request streaming wrapper).
    # Order: last added runs first, so HostGuard sees the request first.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.MAX_REQUEST_BYTES)
    app.add_middleware(RequestContextMiddleware)
    # Exempt the liveness probe: load balancers (AWS ALB) probe by IP, so the Host
    # header is the container's private IP and can never be whitelisted.
    app.add_middleware(
        HostGuardMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
        exempt_paths=("/api/v1/health/live",),
    )

    # Register routers
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(cases.router, prefix="/api/v1/cases", tags=["cases"])
    app.include_router(rag.router, prefix="/api/v1/rag", tags=["rag"])
    app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
    app.include_router(fir_analysis.router, prefix="/api/v1", tags=["fir-analysis"])

    return app


app = create_app()
