import asyncio
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db
from app.schemas.case import CaseSubmit, CaseResponse, CaseListItem, RegenerateRequest, PromptSubmit
from app.services.case_service import CaseService
from app.core.security import get_current_user
from app.models.user import User
from app.utils.pdf_generator import generate_pdf_bytes

logger = logging.getLogger(__name__)
router = APIRouter()


def get_nlp(request: Request):
    return request.app.state.nlp_pipeline


@router.post("/submit", status_code=202)
async def submit_case(
    payload: CaseSubmit,
    background_tasks: BackgroundTasks,
    request: Request,
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
        "message": "Case submitted. AI is generating your draft."
    }


@router.post("/prompt", status_code=202)
async def submit_case_prompt(
    payload: PromptSubmit,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseService(db)
    case = await service.create_case_from_prompt(payload.prompt, current_user)
    nlp = get_nlp(request)
    background_tasks.add_task(_process_case_background, case.id, nlp)
    return {
        "id": case.id,
        "title": case.title,
        "status": case.status,
        "created_at": case.created_at.isoformat(),
        "message": "Prompt received. AI is extracting details and generating your draft."
    }


async def _process_case_background(case_id: str, nlp_pipeline):
    from app.db.postgres import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            service = CaseService(db)
            await service.process_case(case_id, nlp_pipeline)
        except Exception as e:
            logger.error(f"Background processing failed for case {case_id}: {e}")


@router.get("/", response_model=List[CaseListItem])
async def list_cases(
    skip: int = 0,
    limit: int = 20,
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
async def regenerate_section(
    case_id: str,
    payload: RegenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = CaseService(db)
    nlp = get_nlp(request)
    try:
        result = await service.regenerate_section(
            case_id=case_id,
            section=payload.section,
            user=current_user,
            nlp_pipeline=nlp,
            additional_context=payload.additional_context,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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

    content = generate_pdf_bytes(
        case_id=case_id,
        case_type=case.case_type or "Civil",
        sections=case.draft.sections,
    )

    is_pdf = content[:4] == b"%PDF"
    media_type = "application/pdf" if is_pdf else "text/html"
    filename = f"legal_draft_{case_id[:8]}.pdf" if is_pdf else f"legal_draft_{case_id[:8]}.html"

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


@router.get("/{case_id}/progress")
async def stream_progress(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.db.redis_client import get_redis

    service = CaseService(db)
    if not await service.get_case(case_id, current_user):
        raise HTTPException(status_code=404, detail="Case not found")

    async def event_generator():
        r = get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(f"progress:{case_id}")
        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30)
                if msg:
                    data = msg.get("data", "")
                    yield f"data: {data}\n\n"
                    if data in ("completed", "failed"):
                        break
                await asyncio.sleep(0.1)
        finally:
            await pubsub.unsubscribe(f"progress:{case_id}")
            await pubsub.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
