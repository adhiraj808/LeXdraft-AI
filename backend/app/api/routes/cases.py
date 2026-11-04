import asyncio
import logging
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import get_current_user
from app.db.postgres import get_db
from app.models.case import Case
from app.models.user import User
from app.schemas.case import (
    CaseListItem,
    CaseResponse,
    CaseSubmit,
    PromptSubmit,
    RegenerateRequest,
)
from app.services.case_service import CaseService
from app.utils.pdf_generator import generate_pdf_bytes

logger = logging.getLogger(__name__)
router = APIRouter()

TERMINAL_STATUSES = ("completed", "failed")
# Hard cap for one progress stream, so abandoned connections cannot pile up forever.
SSE_MAX_SECONDS = 600
SSE_POLL_SECONDS = 15


def get_nlp(request: Request):
    nlp = getattr(request.app.state, "nlp_pipeline", None)
    if nlp is None:
        raise HTTPException(
            status_code=503, detail="AI pipeline is not initialised yet"
        )
    return nlp


@router.post("/submit", status_code=202)
@limiter.limit(settings.RATE_LIMIT_DRAFTS)
async def submit_case(
    request: Request,
    payload: CaseSubmit,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseService(db)
    case = await service.create_case(payload, current_user)
    nlp = get_nlp(request)
    background_tasks.add_task(_process_case_background, case.id, nlp)
    return {
        "id": case.id,
        "title": case.title,
        "status": case.status,
        "created_at": case.created_at.isoformat(),
        "message": "Case submitted. AI is generating your draft.",
    }


@router.post("/prompt", status_code=202)
@limiter.limit(settings.RATE_LIMIT_DRAFTS)
async def submit_case_prompt(
    request: Request,
    payload: PromptSubmit,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseService(db)
    case = await service.create_case_from_prompt(payload.prompt, current_user)
    nlp = get_nlp(request)
    # AI-chat flow is strict: never serve a template as an "AI draft".
    background_tasks.add_task(_process_case_background, case.id, nlp, True)
    return {
        "id": case.id,
        "title": case.title,
        "status": case.status,
        "created_at": case.created_at.isoformat(),
        "message": "Prompt received. AI is extracting details and generating your draft.",
    }


async def _process_case_background(case_id: str, nlp_pipeline, strict: bool = False):
    from app.db.postgres import AsyncSessionLocal
    from app.db.redis_client import init_redis

    await init_redis()  # Ensure Redis is initialized in background task
    async with AsyncSessionLocal() as db:
        try:
            service = CaseService(db)
            await service.process_case(case_id, nlp_pipeline, strict=strict)
        except Exception as e:
            # process_case already logged the traceback and marked the case as failed.
            logger.error(
                f"Background processing failed for case {case_id}: {type(e).__name__}: {e}"
            )


@router.get("/", response_model=List[CaseListItem])
async def list_cases(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseService(db)
    return await service.list_cases(current_user, skip=skip, limit=limit)


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseService(db)
    case = await service.get_case(case_id, current_user)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post("/{case_id}/regenerate")
@limiter.limit(settings.RATE_LIMIT_DRAFTS)
async def regenerate_section(
    request: Request,
    case_id: str,
    payload: RegenerateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseService(db)
    nlp = get_nlp(request)

    if payload.section == "all":
        # Regenerating all 7 sections takes minutes - longer than a proxy/browser keeps an HTTP
        # request open. Queue it like a new case; the client polls GET /cases/{id} for the result.
        case = await service.get_case(case_id, current_user)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        case.status = "pending"
        await db.commit()
        background_tasks.add_task(_process_case_background, case.id, nlp)
        return JSONResponse(
            status_code=202,
            content={
                "section": "all",
                "status": "pending",
                "message": "Draft regeneration queued.",
            },
        )

    try:
        return await service.regenerate_section(
            case_id=case_id,
            section=payload.section,
            user=current_user,
            nlp_pipeline=nlp,
            additional_context=payload.additional_context,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Regeneration failed for case {case_id}: {e}")
        raise HTTPException(
            status_code=503,
            detail="The AI pipeline is not ready. Please retry shortly.",
        )


@router.get("/{case_id}/export/pdf")
async def export_pdf(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseService(db)
    case = await service.get_case(case_id, current_user)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if not case.draft:
        raise HTTPException(status_code=404, detail="Draft not yet generated")

    # ReportLab is CPU-bound: keep it off the event loop.
    content = await asyncio.to_thread(
        generate_pdf_bytes,
        case_id=case.id,
        case_type=case.case_type or "Civil",
        sections=case.draft.sections,
    )

    is_pdf = content[:4] == b"%PDF"
    media_type = "application/pdf" if is_pdf else "text/html"
    filename = (
        f"legal_draft_{case.id[:8]}.pdf"
        if is_pdf
        else f"legal_draft_{case.id[:8]}.html"
    )

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{case_id}", status_code=204)
async def delete_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseService(db)
    deleted = await service.delete_case(case_id, current_user)
    if not deleted:
        raise HTTPException(status_code=404, detail="Case not found")


async def _case_status(case_id: str):
    """Current status using a short-lived session (never held open while streaming)."""
    from app.db.postgres import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        return (
            await session.execute(select(Case.status).where(Case.id == case_id))
        ).scalar_one_or_none()


@router.get("/{case_id}/progress")
async def stream_progress(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.db.redis_client import get_redis

    service = CaseService(db)
    case = await service.get_case(case_id, current_user)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    initial_status = case.status
    channel = f"progress:{case_id}"

    async def event_generator():
        # Already finished: nothing will ever be published, so answer immediately instead of hanging.
        if initial_status in TERMINAL_STATUSES:
            yield f"data: {initial_status}\n\n"
            return

        loop = asyncio.get_running_loop()
        deadline = loop.time() + SSE_MAX_SECONDS
        pubsub = get_redis().pubsub()
        await pubsub.subscribe(channel)
        try:
            while loop.time() < deadline:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=SSE_POLL_SECONDS
                )
                if msg:
                    data = msg.get("data", "")
                    yield f"data: {data}\n\n"
                    if data in TERMINAL_STATUSES:
                        return
                    continue
                # Quiet period: re-check the database in case the final event was published
                # before we subscribed (or the processing task died).
                status = await _case_status(case_id)
                if status is None or status in TERMINAL_STATUSES:
                    yield f"data: {status or 'failed'}\n\n"
                    return
                yield ": keep-alive\n\n"
        finally:
            await pubsub.unsubscribe(channel)
            closer = getattr(pubsub, "aclose", None) or pubsub.close
            await closer()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
