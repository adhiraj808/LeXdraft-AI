from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    set_auth_cookies,
    clear_auth_cookies,
    blacklist_token,
)
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
    request: Request, response: Response, payload: UserCreate, db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    user = await service.register(payload)
    # Auto-login after registration
    tokens = await service.login(payload.username, payload.password)
    set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return user


@router.post("/login", response_model=Token)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(
    request: Request, response: Response, payload: UserLogin, db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    result = await service.login(payload.username, payload.password)
    set_auth_cookies(response, result["access_token"], result["refresh_token"])
    return result


@router.post("/refresh", response_model=Token)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def refresh_token(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    """Rotate refresh token: issue new access + refresh pair, blacklist old refresh token."""
    # Get refresh token from cookie (httpOnly, not accessible via JS)
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        # Fallback to header for API clients
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            refresh_token = auth_header[7:]

    if not refresh_token:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type")
        user_id = payload.get("sub")
        jti = payload.get("jti")
    except (ValueError, Exception):
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Blacklist the old refresh token
    if jti:
        from datetime import datetime, timezone
        exp_timestamp = payload.get("exp")
        if exp_timestamp:
            expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
            await blacklist_token(db, jti, expires_at)

    # Verify user still exists and is active
    result = await db.execute(
        User.__table__.select().where(User.id == user_id)
    )
    # Use ORM for proper relationship loading
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Issue new token pair
    new_access = create_access_token({"sub": user.id, "username": user.username})
    new_refresh = create_refresh_token({"sub": user.id, "username": user.username})
    set_auth_cookies(response, new_access, new_refresh)

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/logout")
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def logout(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    """Logout: blacklist both access and refresh tokens, clear cookies."""
    # Blacklist access token if present
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        access_token = auth_header[7:]
        try:
            payload = decode_token(access_token)
            jti = payload.get("jti")
            if jti:
                from datetime import datetime, timezone
                exp_timestamp = payload.get("exp")
                if exp_timestamp:
                    expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
                    await blacklist_token(db, jti, expires_at)
        except Exception:
            pass  # Token may be invalid, but we still clear cookies

    # Blacklist refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            jti = payload.get("jti")
            if jti:
                from datetime import datetime, timezone
                exp_timestamp = payload.get("exp")
                if exp_timestamp:
                    expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
                    await blacklist_token(db, jti, expires_at)
        except Exception:
            pass

    clear_auth_cookies(response)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/google", response_model=Token)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def google_auth(
    request: Request, response: Response, payload: GoogleAuthRequest, db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    result = await service.google_login(payload.credential)
    set_auth_cookies(response, result["access_token"], result["refresh_token"])
    return result