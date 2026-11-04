from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import get_current_user
from app.db.postgres import get_db
from app.models.user import User
from app.schemas.user import (
    GoogleAuthRequest,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()


# Brute-force / credential-stuffing guard: strict per-IP limits on every credential endpoint.
@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def register(
    request: Request, payload: UserCreate, db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    user = await service.register(payload)
    return user


@router.post("/login", response_model=Token)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(
    request: Request, payload: UserLogin, db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    result = await service.login(payload.username, payload.password)
    return result


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/google", response_model=Token)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def google_auth(
    request: Request, payload: GoogleAuthRequest, db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    return await service.google_login(payload.credential)
