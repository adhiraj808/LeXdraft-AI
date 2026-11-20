"""JWT authentication and password hashing utilities."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.postgres import get_db
from app.models.user import User
from app.models.token_blacklist import TokenBlacklist

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# bcrypt silently ignores everything after the 72nd byte (and newer releases raise).
MAX_PASSWORD_BYTES = 72

_dummy_hash: Optional[str] = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# bcrypt is deliberately slow (~0.1-0.3 s of CPU). Run it in a worker thread so a
# login/registration burst does not freeze every other request on the event loop.
async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    return await asyncio.to_thread(verify_password, plain_password, hashed_password)


async def get_password_hash_async(password: str) -> str:
    return await asyncio.to_thread(get_password_hash, password)


async def burn_password_check(plain_password: str) -> None:
    """Spend the same time as a real verification.

    Called when the username does not exist so response time does not reveal which
    usernames are registered.
    """
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = await get_password_hash_async("timing-equalisation-placeholder")
    await verify_password_async(plain_password, _dummy_hash)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access", "jti": str(uuid4())})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    to_encode.update({"exp": expire, "type": "refresh", "jti": str(uuid4())})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def is_token_blacklisted(db: AsyncSession, jti: str) -> bool:
    """Check if a token JTI is blacklisted."""
    result = await db.execute(select(TokenBlacklist).where(TokenBlacklist.jti == jti))
    return result.scalar_one_or_none() is not None


async def blacklist_token(db: AsyncSession, jti: str, expires_at: datetime) -> None:
    """Add a token JTI to the blacklist."""
    blacklist_entry = TokenBlacklist(jti=jti, expires_at=expires_at)
    db.add(blacklist_entry)
    await db.commit()


async def get_current_user(
    request: Request,
    response: Response,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency: extracts and validates current user from JWT."""
    payload = decode_token(token)
    user_id = payload.get("sub")
    token_type = payload.get("type")
    jti = payload.get("jti")

    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    if token_type != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    # Check if token is blacklisted
    if jti and await is_token_blacklisted(db, jti):
        raise HTTPException(status_code=401, detail="Token has been revoked")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        # A blocked/deactivated account must lose access immediately, not when its token expires.
        raise HTTPException(status_code=403, detail="Account is inactive")

    request.state.user_id = user.id
    return user


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set httpOnly, secure cookies for auth tokens."""
    # Access token cookie (short-lived)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=not settings.DEBUG,  # Secure in production
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    # Refresh token cookie (long-lived)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/api/v1/auth",
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear auth cookies on logout."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")


def get_token_from_cookie_or_header(
    request: Request,
    access_token_cookie: Optional[str] = None,
) -> Optional[str]:
    """Extract token from cookie (preferred) or Authorization header."""
    # Try cookie first (httpOnly, not accessible via JS)
    if access_token_cookie:
        return access_token_cookie
    # Fallback to Authorization header for API clients
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None