"""Admin endpoints: view + manage all users, cases, drafts, and AI configuration.

Access: only users with role == "admin" (403 otherwise).
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_current_user
from app.db.postgres import get_db
from app.db.redis_client import delete_case_cache
from app.models.case import Case, Draft
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_MODELS = 50


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return current_user


def audit_log(admin_user: User, action: str, target: str, details: dict = None):
    """Log admin actions for audit trail."""
    audit_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": str(uuid.uuid4())[:8],
        "admin_id": admin_user.id,
        "admin_username": admin_user.username,
        "action": action,
        "target": target,
        "details": details or {},
    }
    logger.info(f"AUDIT: {audit_entry}")
    return audit_entry


# ---------- Pydantic Models ----------


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


class ModelAdd(BaseModel):
    id: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_.:-]+$")
    label: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9_.-]+$")


class AdminStatusResponse(BaseModel):
    enabled: bool
    model: str
    blocked_users: List[str]
    models: List[dict]


class BlockUserRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    remove_data: bool = False


class UnblockUserRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)


class DeleteUserDataRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)


class ToggleLLMResponse(BaseModel):
    enabled: bool


class SetModelRequest(BaseModel):
    model: str = Field(min_length=1, max_length=50)


class SetModelResponse(BaseModel):
    model: str


class AddModelResponse(BaseModel):
    success: bool
    models: List[dict]


class ModelsResponse(BaseModel):
    success: bool
    models: List[dict]


# ---------- Global AI State (in-memory, resets on restart) ----------
LLM_ENABLED = True
CURRENT_MODEL = getattr(settings, "MODEL_PROVIDER", "groq") or "groq"

AVAILABLE_MODELS = [
    {"id": "groq", "label": "Groq (Llama 3.1 70B)", "provider": "groq"},
    {"id": "hf", "label": "HuggingFace (Llama 3.2 1B)", "provider": "hf"},
    {"id": "local", "label": "Local GGUF (if available)", "provider": "local"},
    {"id": "template", "label": "Template Fallback", "provider": "template"},
]


# ---------- Helpers ----------


async def _get_user_or_404(db: AsyncSession, user_id: str) -> User:
    user = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def _delete_user_cases(db: AsyncSession, user_id: str) -> List[str]:
    """Delete every case (and its draft) of a user with bulk statements.

    Returns the deleted case ids so the caller can clear their cache entries once the
    transaction has been committed.
    """
    case_ids = list(
        (await db.execute(select(Case.id).where(Case.user_id == user_id)))
        .scalars()
        .all()
    )
    if case_ids:
        keep_session_state = {"synchronize_session": False}
        await db.execute(
            delete(Draft)
            .where(Draft.case_id.in_(select(Case.id).where(Case.user_id == user_id)))
            .execution_options(**keep_session_state)
        )
        await db.execute(
            delete(Case)
            .where(Case.user_id == user_id)
            .execution_options(**keep_session_state)
        )
    return case_ids


async def _forget_cached_cases(case_ids: List[str]) -> None:
    for case_id in case_ids:
        await delete_case_cache(case_id)  # best-effort helper: never raises


# ---------- Admin Routes ----------


@router.get("/users", response_model=List[AdminUserItem])
async def admin_list_users(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    users = (await db.execute(select(User).order_by(User.created_at))).scalars().all()
    counts = dict(
        (
            await db.execute(
                select(Case.user_id, func.count(Case.id)).group_by(Case.user_id)
            )
        ).all()
    )
    return [
        AdminUserItem(
            id=u.id,
            email=u.email,
            username=u.username,
            full_name=u.full_name,
            role=u.role,
            is_active=u.is_active,
            created_at=u.created_at,
            case_count=counts.get(u.id, 0),
        )
        for u in users
    ]


@router.patch("/users/{user_id}", response_model=AdminUserItem)
async def admin_set_role(
    request: Request,
    user_id: str,
    payload: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if payload.role not in ("admin", "advocate"):
        raise HTTPException(status_code=400, detail="role must be admin or advocate")
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    user = await _get_user_or_404(db, user_id)
    old_role = user.role
    user.role = payload.role
    await db.commit()
    await db.refresh(user)
    case_count = (
        await db.execute(select(func.count(Case.id)).where(Case.user_id == user.id))
    ).scalar_one()
    audit_log(
        admin,
        "update_user_role",
        "user",
        {"user_id": user_id, "old_role": old_role, "new_role": payload.role},
    )
    return AdminUserItem(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        case_count=case_count,
    )


@router.delete("/users/{user_id}", status_code=204)
async def admin_delete_user(
    request: Request,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = await _get_user_or_404(db, user_id)
    email = user.email
    case_ids = await _delete_user_cases(db, user_id)
    await db.execute(
        delete(User)
        .where(User.id == user_id)
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    await _forget_cached_cases(case_ids)
    audit_log(
        admin,
        "delete_user",
        "user",
        {"user_id": user_id, "email": email, "cases_deleted": len(case_ids)},
    )


@router.get("/cases", response_model=List[AdminCaseItem])
async def admin_list_cases(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
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
            id=case.id,
            title=case.title,
            case_type=case.case_type,
            status=case.status,
            user_id=case.user_id,
            user_email=email or "",
            has_draft=draft_id is not None,
            model_used=model_used,
            created_at=case.created_at,
        )
        for case, email, draft_id, model_used in rows
    ]


@router.delete("/cases/{case_id}", status_code=204)
async def admin_delete_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    owner_id = (
        await db.execute(select(Case.user_id).where(Case.id == case_id))
    ).scalar_one_or_none()
    if owner_id is None:
        raise HTTPException(status_code=404, detail="Case not found")
    await db.execute(
        delete(Draft)
        .where(Draft.case_id == case_id)
        .execution_options(synchronize_session=False)
    )
    await db.execute(
        delete(Case)
        .where(Case.id == case_id)
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    await delete_case_cache(case_id)
    audit_log(admin, "delete_case", "case", {"case_id": case_id, "owner_id": owner_id})


@router.post("/cases/{case_id}/reprocess", status_code=202)
async def admin_reprocess_case(
    case_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Reset a stuck/failed case to pending and queue it for processing again."""
    from app.api.routes.cases import _process_case_background, get_nlp

    case = (
        await db.execute(select(Case).where(Case.id == case_id))
    ).scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    nlp = get_nlp(request)
    case.status = "pending"
    await db.commit()
    background_tasks.add_task(_process_case_background, case.id, nlp)
    audit_log(admin, "reprocess_case", "case", {"case_id": case_id})
    return {
        "id": case.id,
        "status": "pending",
        "message": "Case queued for processing again.",
    }


# ---------- AI Configuration Routes ----------


@router.get("/status", response_model=AdminStatusResponse)
async def admin_status(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Get current AI configuration status."""
    blocked = (
        (
            await db.execute(
                select(User.username)
                .where(User.is_active.is_(False))
                .order_by(User.username)
            )
        )
        .scalars()
        .all()
    )
    return AdminStatusResponse(
        enabled=LLM_ENABLED,
        model=CURRENT_MODEL,
        blocked_users=list(blocked),
        models=AVAILABLE_MODELS,
    )


@router.post("/toggle-llm", response_model=ToggleLLMResponse)
async def admin_toggle_llm(request: Request, admin: User = Depends(require_admin)):
    """Enable/disable AI draft generation entirely."""
    global LLM_ENABLED
    LLM_ENABLED = not LLM_ENABLED
    audit_log(admin, "toggle_llm", "system", {"enabled": LLM_ENABLED})
    logger.info(f"Admin toggled LLM: {'enabled' if LLM_ENABLED else 'disabled'}")
    return ToggleLLMResponse(enabled=LLM_ENABLED)


@router.post("/set-model", response_model=SetModelResponse)
async def admin_set_model(
    request: Request,
    payload: SetModelRequest,
    admin: User = Depends(require_admin),
):
    """Set the default AI model for draft generation."""
    global CURRENT_MODEL
    if not any(m["id"] == payload.model for m in AVAILABLE_MODELS):
        raise HTTPException(
            status_code=400, detail=f"Model {payload.model} not in available models"
        )
    CURRENT_MODEL = payload.model
    audit_log(admin, "set_model", "system", {"model": CURRENT_MODEL})
    logger.info(f"Admin set default model to: {CURRENT_MODEL}")
    return SetModelResponse(model=CURRENT_MODEL)


@router.post("/add-model", response_model=AddModelResponse)
async def admin_add_model(
    request: Request,
    payload: ModelAdd,
    admin: User = Depends(require_admin),
):
    """Add a new model to the available models list."""
    if any(m["id"] == payload.id for m in AVAILABLE_MODELS):
        raise HTTPException(
            status_code=400, detail=f"Model with id {payload.id} already exists"
        )
    if len(AVAILABLE_MODELS) >= MAX_MODELS:
        raise HTTPException(
            status_code=400, detail=f"At most {MAX_MODELS} models can be registered"
        )
    AVAILABLE_MODELS.append(
        {"id": payload.id, "label": payload.label, "provider": payload.provider}
    )
    audit_log(
        admin,
        "add_model",
        "system",
        {"model_id": payload.id, "label": payload.label, "provider": payload.provider},
    )
    logger.info(f"Admin added model: {payload.id} ({payload.label})")
    return AddModelResponse(success=True, models=AVAILABLE_MODELS)


@router.get("/models", response_model=ModelsResponse)
async def admin_get_models(admin: User = Depends(require_admin)):
    """Get all available models."""
    return ModelsResponse(success=True, models=AVAILABLE_MODELS)


@router.delete("/models/{model_id}")
async def admin_delete_model(
    model_id: str,
    admin: User = Depends(require_admin),
):
    """Delete a model from the available models list."""
    global AVAILABLE_MODELS
    # Prevent deletion of core models
    core_models = {"groq", "hf", "local", "template"}
    if model_id in core_models:
        raise HTTPException(
            status_code=400, detail=f"Cannot delete core model: {model_id}"
        )
    if not any(m["id"] == model_id for m in AVAILABLE_MODELS):
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    AVAILABLE_MODELS = [m for m in AVAILABLE_MODELS if m["id"] != model_id]
    audit_log(admin, "delete_model", "system", {"model_id": model_id})
    logger.info(f"Admin deleted model: {model_id}")
    return {"success": True, "models": AVAILABLE_MODELS}


# ---------- User Management ----------


@router.post("/block-user")
async def admin_block_user(
    request: Request,
    payload: BlockUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Deactivate a user (their token stops working immediately) and optionally delete their data."""
    if payload.user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot block yourself")
    user = await _get_user_or_404(db, payload.user_id)
    if user.role == "admin":
        raise HTTPException(
            status_code=400, detail="Cannot block an admin; remove the admin role first"
        )
    user.is_active = False
    case_ids: List[str] = []
    if payload.remove_data:
        case_ids = await _delete_user_cases(db, user.id)
    await db.commit()
    await _forget_cached_cases(case_ids)
    audit_log(
        admin,
        "block_user",
        "user",
        {"user_id": payload.user_id, "remove_data": payload.remove_data},
    )
    return {"success": True, "message": f"User {user.username} blocked"}


@router.post("/unblock-user")
async def admin_unblock_user(
    request: Request,
    payload: UnblockUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Re-activate a blocked user."""
    user = await _get_user_or_404(db, payload.user_id)
    user.is_active = True
    await db.commit()
    audit_log(admin, "unblock_user", "user", {"user_id": payload.user_id})
    return {"success": True, "message": f"User {user.username} unblocked"}


@router.post("/delete-user-data")
async def admin_delete_user_data(
    request: Request,
    payload: DeleteUserDataRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Delete all cases and drafts of a user (the account itself is kept)."""
    user = await _get_user_or_404(db, payload.user_id)
    case_ids = await _delete_user_cases(db, user.id)
    await db.commit()
    await _forget_cached_cases(case_ids)
    audit_log(
        admin,
        "delete_user_data",
        "user",
        {"user_id": payload.user_id, "cases_deleted": len(case_ids)},
    )
    return {
        "success": True,
        "message": f"Deleted {len(case_ids)} case(s) of {user.username}",
    }


@router.get("/models-public", response_model=ModelsResponse)
async def get_models_public():
    """Public endpoint for frontend to fetch available models."""
    return ModelsResponse(success=True, models=AVAILABLE_MODELS)
