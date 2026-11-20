"""Arq worker for background case processing."""

import logging
from arq import create_pool
from arq.connections import RedisSettings

from app.core.config import settings
from app.db.postgres import AsyncSessionLocal
from app.services.case_service import CaseService

logger = logging.getLogger(__name__)

# Redis connection pool for Arq
_arq_redis = None


async def get_arq_redis():
    """Get or create Arq Redis connection pool."""
    global _arq_redis
    if _arq_redis is None:
        _arq_redis = await create_pool(
            RedisSettings(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD or None,
                database=settings.REDIS_DB,
            )
        )
    return _arq_redis


async def close_arq_redis():
    """Close Arq Redis connection pool."""
    global _arq_redis
    if _arq_redis:
        await _arq_redis.close(close_connection_pool=True)
        _arq_redis = None


async def process_case_job(ctx: dict, case_id: str) -> dict:
    """
    Arq job to process a case through the NLP pipeline.
    
    This replaces the in-process BackgroundTasks approach.
    """
    logger.info(f"Starting Arq job for case {case_id}")
    
    # Create a new database session for this job
    async with AsyncSessionLocal() as db:
        service = CaseService(db)
        try:
            nlp_pipeline = ctx.get("nlp_pipeline")
            if nlp_pipeline is None:
                from app.nlp.pipeline import get_nlp
                nlp_pipeline = await get_nlp()
            result = await service.process_case(case_id, nlp_pipeline)
            logger.info(f"Arq job completed for case {case_id}: {result}")
            return {"status": "success", "case_id": case_id, "result": result}
        except Exception as e:
            logger.error(f"Arq job failed for case {case_id}: {e}", exc_info=True)
            # The service will handle marking the case as failed
            await service.mark_case_failed(case_id, str(e))
            return {"status": "failed", "case_id": case_id, "error": str(e)}


async def enqueue_case_processing(case_id: str) -> str:
    """
    Enqueue a case for background processing via Arq.
    
    Returns the job ID.
    """
    redis = await get_arq_redis()
    job = await redis.enqueue_job("process_case_job", case_id)
    logger.info(f"Enqueued case {case_id} for processing, job_id={job.job_id}")
    return job.job_id


# Arq worker settings
class WorkerSettings:
    functions = [process_case_job]
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD or None,
        database=settings.REDIS_DB,
    )
    # Process up to MAX_CONCURRENT_DRAFTS jobs concurrently
    max_jobs = settings.MAX_CONCURRENT_DRAFTS
    # Job timeout (5 minutes)
    job_timeout = 300
    # Keep result for 1 hour
    keep_result = 3600
    # Health check interval
    health_check_interval = 30
    # Poll interval
    poll_interval = 1.0