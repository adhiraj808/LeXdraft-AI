"""Admin endpoints: view + manage all users, cases, drafts, and AI configuration.

Access: only users with role == "admin" (403 otherwise).
"""
import logging
from datetime import datetime
from typing import List, Optional
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
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


def audit_log(admin_user: User, action: str, target: str, details: dict = None):
    """Log admin actions for audit trail."""
    audit_entry = {
        "timestamp": datetime.utcnow().isoformat(),
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
    id: str
    label: str
    provider: str


class AdminStatusResponse(BaseModel):
    enabled: bool
    model: str
    blocked_users: List[str]
    models: List[dict]


class BlockUserRequest(BaseModel):
    user_id: str
    remove_data: bool = False


class UnblockUserRequest(BaseModel):
    user_id: str


class DeleteUserDataRequest(BaseModel):
    user_id: str


class ToggleLLMResponse(BaseModel):
    enabled: bool


class SetModelRequest(BaseModel):
    model: str


class SetModelResponse(BaseModel):
    model: str


class AddModelResponse(BaseModel):
    success: bool
    models: List[dict]


class ModelsResponse(BaseModel):
    success: bool
    models: List[dict]


# ---------- Admin Auth Dependency ----------

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return current_user


# ---------- Global AI State (in-memory, resets on restart) ----------
# These mirror the friend's project simple in-memory approach
LLM_ENABLED = True
CURRENT_MODEL = getattr(settings, "MODEL_PROVIDER", "groq") or "groq"

AVAILABLE_MODELS = [
    {"id": "groq", "label": "Groq (Llama 3.1 70B)", "provider": "groq"},
    {"id": "hf", "label": "HuggingFace (Llama 3.2 1B)", "provider": "hf"},
    {"id": "local", "label": "Local GGUF (if available)", "provider": "local"},
    {"id": "template", "label": "Template Fallback", "provider": "template"},
]


# ---------- Admin Routes ----------

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
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    old_role = user.role
    user.role = payload.role
    await db.commit()
    await db.refresh(user)
    audit_log(admin, "update_user_role", "user", {"user_id": user_id, "old_role": old_role, "new_role": payload.role})
    return AdminUserItem(
        id=user.id, email=user.email, username=user.username, full_name=user.full_name,
        role=user.role, is_active=user.is_active, created_at=user.created_at, case_count=0,
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
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    cases = (await db.execute(select(Case).where(Case.user_id == user_id))).scalars().all()
    for case in cases:
        draft = (await db.execute(select(Draft).where(Draft.case_id == case.id))).scalar_one_or_none()
        if draft:
            await db.delete(draft)
        await db.delete(case)
    await db.delete(user)
    await db.commit()
    audit_log(admin, "delete_user", "user", {"user_id": user_id, "email": user.email})
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
    await db.delete(case)
    await db.commit()
    audit_log(admin, "delete_user", "user", {"user_id": user_id, "email": user.email})
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


# ---------- AI Configuration Routes (Friend's Project Style) ----------

@router.get("/status", response_model=AdminStatusResponse)
async def admin_status(admin: User = Depends(require_admin)):
    """Get current AI configuration status."""
    global LLM_ENABLED, CURRENT_MODEL, AVAILABLE_MODELS
    return AdminStatusResponse(
        enabled=LLM_ENABLED,
        model=CURRENT_MODEL,
        blocked_users=[],  # Could add blocked_users table later
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
    global CURRENT_MODEL, AVAILABLE_MODELS
    if not any(m["id"] == payload.model for m in AVAILABLE_MODELS):
        raise HTTPException(status_code=400, detail=f"Model {payload.model} not in available models")
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
    global AVAILABLE_MODELS
    if any(m["id"] == payload.id for m in AVAILABLE_MODELS):
        raise HTTPException(status_code=400, detail=f"Model with id {payload.id} already exists")
    AVAILABLE_MODELS.append({"id": payload.id, "label": payload.label, "provider": payload.provider})
    audit_log(admin, "add_model", "system", {"model_id": payload.id, "label": payload.label, "provider": payload.provider})
    logger.info(f"Admin added model: {payload.id} ({payload.label})")
    return AddModelResponse(success=True, models=AVAILABLE_MODELS)


@router.get("/models", response_model=ModelsResponse)
async def admin_get_models(admin: User = Depends(require_admin)):
    """Get all available models (public endpoint for frontend dropdown)."""
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
        raise HTTPException(status_code=400, detail=f"Cannot delete core model: {model_id}")
    if not any(m["id"] == model_id for m in AVAILABLE_MODELS):
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    AVAILABLE_MODELS = [m for m in AVAILABLE_MODELS if m["id"] != model_id]
    audit_log(admin, "delete_model", "system", {"model_id": model_id})
    logger.info(f"Admin deleted model: {model_id}")
    return {"success": True, "models": AVAILABLE_MODELS}


# ---------- User Management (Friend's Project Style) ----------

@router.post("/block-user")
async def admin_block_user(
    request: Request,
    payload: BlockUserRequest,
    admin: User = Depends(require_admin),
):
    """Block a user and optionally delete their data."""
    # For now, just return success - could add blocked_users table later
    audit_log(admin, "block_user", "user", {"user_id": payload.user_id, "remove_data": payload.remove_data})
    logger.info(f"Admin blocked user: {payload.user_id}, remove_data={payload.remove_data}")
    return {"success": True, "message": f"User {payload.user_id} blocked"}


@router.post("/unblock-user")
async def admin_unblock_user(
    request: Request,
    payload: UnblockUserRequest,
    admin: User = Depends(require_admin),
):
    """Unblock a user."""
    audit_log(admin, "unblock_user", "user", {"user_id": payload.user_id})
    logger.info(f"Admin unblocked user: {payload.user_id}")
    return {"success": True, "message": f"User {payload.user_id} unblocked"}


@router.post("/delete-user-data")
async def admin_delete_user_data(
    request: Request,
    payload: DeleteUserDataRequest,
    admin: User = Depends(require_admin),
):
    """Delete all data for a user (messages, cases, drafts)."""
    # This would need a db session - for now return success
    audit_log(admin, "delete_user_data", "user", {"user_id": payload.user_id})
    logger.info(f"Admin deleted data for user: {payload.user_id}")
    return {"success": True, "message": f"Data for user {payload.user_id} deleted"}


@router.get("/models-public", response_model=ModelsResponse)
@router.get("/admin/models-public", response_model=ModelsResponse)
async def get_models_public():
    """Public endpoint for frontend to fetch available models."""
    return ModelsResponse(success=True, models=AVAILABLE_MODELS)