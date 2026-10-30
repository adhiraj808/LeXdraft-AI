"""
AI-Powered Legal Case Drafting System
FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import asyncio
import uuid

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.rate_limit import limiter, public_limiter
from app.db.postgres import init_db
from app.db.redis_client import init_redis
from app.nlp.pipeline import NLPPipeline
from app.api.routes import admin, auth, cases, health, rag, fir_analysis

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
    logger.info("About to init_db...")
    await init_db()
    logger.info("PostgreSQL connected.")

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

    # Security middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "0.0.0.0"]
    )

    # Request size limit middleware
    @app.middleware("http")
    async def limit_request_size(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 1_048_576:  # 1MB limit
            return Response("Payload too large", status_code=413)
        return await call_next(request)

    # Request ID middleware for tracing
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    # Add rate limiter middleware
    from slowapi.middleware import SlowAPIMiddleware
    app.add_middleware(SlowAPIMiddleware)

    # Public rate limiter for public endpoints
    app.state.public_limiter = public_limiter

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
    app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
    app.include_router(fir_analysis.router, prefix="/api/v1", tags=["fir-analysis"])

    return app


app = create_app()
