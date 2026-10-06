"""Admin endpoints: view + manage all users, cases and drafts.

Access: only users with role == "admin" (403 otherwise).
"""
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.postgres import get_db
from app.db.redis_client import delete_case_cache
from app.models.case import Case, Draft
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return current_user


class AdminUserItem(BaseModel):
    id: str
    email: str
    username: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    case_count: int = 0

    class Config:
        from_attributes = True


class AdminCaseItem(BaseModel):
    id: str
    title: str
    case_type: Optional[str] = None
    status: str
    user_id: str
    user_email: str = ""
    has_draft: bool = False
    model_used: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RoleUpdate(BaseModel):
    role: str


@router.get("/users", response_model=List[AdminUserItem])
async def admin_list_users(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    users = (await db.execute(select(User).order_by(User.created_at))).scalars().all()
    counts = dict(
        (await db.execute(
            select(Case.user_id, func.count(Case.id)).group_by(Case.user_id)
        )).all()
    )
    return [
        AdminUserItem(
            id=u.id, email=u.email, username=u.username, full_name=u.full_name,
            role=u.role, is_active=u.is_active, created_at=u.created_at,
            case_count=counts.get(u.id, 0),
        )
        for u in users
    ]


@router.patch("/users/{user_id}", response_model=AdminUserItem)
async def admin_set_role(
    user_id: str,
    payload: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if payload.role not in ("admin", "advocate"):
        raise HTTPException(status_code=400, detail="role must be admin or advocate")
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = payload.role
    await db.commit()
    await db.refresh(user)
    return AdminUserItem(
        id=user.id, email=user.email, username=user.username, full_name=user.full_name,
        role=user.role, is_active=user.is_active, created_at=user.created_at, case_count=0,
    )


@router.delete("/users/{user_id}", status_code=204)
async def admin_delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    cases = (await db.execute(select(Case).where(Case.user_id == user_id))).scalars().all()
    for case in cases:
        draft = (await db.execute(select(Draft).where(Draft.case_id == case.id))).scalar_one_or_none()
        if draft:
            await db.delete(draft)
        await delete_case_cache(case.id)
        await db.delete(case)
    await db.delete(user)
    await db.commit()
    return None


@router.get("/cases", response_model=List[AdminCaseItem])
async def admin_list_cases(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    rows = (
        await db.execute(
            select(Case, User.email, Draft.id, Draft.model_used)
            .join(User, User.id == Case.user_id)
            .outerjoin(Draft, Draft.case_id == Case.id)
            .order_by(Case.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
    ).all()
    return [
        AdminCaseItem(
            id=case.id, title=case.title, case_type=case.case_type, status=case.status,
            user_id=case.user_id, user_email=email or "", has_draft=draft_id is not None,
            model_used=model_used, created_at=case.created_at,
        )
        for case, email, draft_id, model_used in rows
    ]


@router.delete("/cases/{case_id}", status_code=204)
async def admin_delete_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    draft = (await db.execute(select(Draft).where(Draft.case_id == case_id))).scalar_one_or_none()
    if draft:
        await db.delete(draft)
    await delete_case_cache(case_id)
    await db.delete(case)
    await db.commit()
    return None


@router.post("/cases/{case_id}/reprocess", status_code=202)
async def admin_reprocess_case(
    case_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Reset a stuck/failed case to pending and queue it for processing again."""
    from app.api.routes.cases import _process_case_background

    case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    case.status = "pending"
    await db.commit()
    nlp = request.app.state.nlp_pipeline
    background_tasks.add_task(_process_case_background, case.id, nlp)
    logger.info(f"Admin {admin.username} queued reprocess for case {case_id}")
    return {"id": case.id, "status": "pending", "message": "Case queued for processing again."}
