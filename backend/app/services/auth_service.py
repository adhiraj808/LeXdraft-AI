"""Authentication business logic."""

import asyncio
import logging
import re
import uuid
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    burn_password_check,
    create_access_token,
    get_password_hash_async,
    verify_password_async,
)
from app.models.user import User
from app.schemas.user import UserCreate

logger = logging.getLogger(__name__)

_google_request: Optional[Any] = None


def _verify_google_credential(credential: str) -> Dict[str, Any]:
    """Blocking Google ID-token verification (run it with asyncio.to_thread).

    The Google/requests libraries are imported lazily: they cost memory and import time
    that deployments without Google sign-in never need.
    """
    global _google_request
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    if _google_request is None:
        _google_request = google_requests.Request()
    return google_id_token.verify_oauth2_token(
        credential, _google_request, settings.GOOGLE_CLIENT_ID
    )


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, payload: UserCreate) -> User:
        email = payload.email.strip().lower()

        # .first(), not scalar_one_or_none(): the email can belong to one user and the
        # username to another, which yields two rows (and would raise -> HTTP 500).
        existing = await self.db.execute(
            select(User.id).where(
                (func.lower(User.email) == email) | (User.username == payload.username)
            )
        )
        if existing.first() is not None:
            raise self._already_registered()

        user = User(
            id=str(uuid.uuid4()),
            email=email,
            username=payload.username,
            hashed_password=await get_password_hash_async(payload.password),
            full_name=payload.full_name,
        )
        self.db.add(user)
        try:
            await self.db.commit()
        except IntegrityError:
            # Lost a race with a concurrent registration of the same email/username.
            await self.db.rollback()
            raise self._already_registered()
        await self.db.refresh(user)
        return user

    @staticmethod
    def _already_registered() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered",
        )

    async def login(self, username: str, password: str) -> dict:
        result = await self.db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if user is None or not user.hashed_password:
            await burn_password_check(
                password
            )  # same response time whether or not the user exists
            raise self._bad_credentials()
        if not await verify_password_async(password, user.hashed_password):
            raise self._bad_credentials()
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is inactive")

        token = create_access_token({"sub": user.id, "username": user.username})
        return {"access_token": token, "token_type": "bearer", "user": user}

    @staticmethod
    def _bad_credentials() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    async def google_login(self, credential: str) -> dict:
        """Verify a Google Identity Services credential and log in or sign up the user."""
        if not settings.GOOGLE_CLIENT_ID:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google sign-in is not configured on this server",
            )
        try:
            id_info = await asyncio.to_thread(_verify_google_credential, credential)
        except ValueError as e:
            logger.warning(f"Google credential verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google credential",
            )
        except (
            Exception
        ) as e:  # network failure while fetching Google's signing certificates, ...
            logger.error(f"Google credential verification unavailable: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not reach Google to verify the credential. Try again shortly.",
            )

        if not id_info.get("email_verified"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google email is not verified",
            )

        google_sub = id_info["sub"]
        email = id_info["email"].strip().lower()

        user = await self._find_google_user(google_sub)
        if user is None:
            try:
                user = await self._link_or_create_google_user(
                    google_sub, email, id_info.get("name")
                )
            except IntegrityError:
                # A concurrent first sign-in created the account between our SELECT and INSERT.
                await self.db.rollback()
                user = await self._find_google_user(google_sub)
                if user is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Could not complete sign-in, retry",
                    )

        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is inactive")

        token = create_access_token({"sub": user.id, "username": user.username})
        return {"access_token": token, "token_type": "bearer", "user": user}

    async def _find_google_user(self, google_sub: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.google_sub == google_sub)
        )
        return result.scalar_one_or_none()

    async def _link_or_create_google_user(
        self, google_sub: str, email: str, full_name: Optional[str]
    ) -> User:
        result = await self.db.execute(
            select(User).where(func.lower(User.email) == email)
        )
        user = result.scalar_one_or_none()
        if user is not None:
            # An account with this (Google-verified) email already exists: link it.
            # Local sign-up never verifies the email, so someone else may have registered it
            # first, knowing its password ("account pre-hijacking"). Dropping the local password
            # leaves Google - which proves ownership of the mailbox - as the only way in.
            user.google_sub = google_sub
            user.hashed_password = None
            user.auth_provider = "google"
        else:
            user = User(
                id=str(uuid.uuid4()),
                email=email,
                username=await self._unique_username_from_email(email),
                hashed_password=None,
                full_name=(full_name or None),
                auth_provider="google",
                google_sub=google_sub,
            )
            self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def _unique_username_from_email(self, email: str) -> str:
        local_part = email.split("@")[0].lower()
        base = re.sub(r"[^a-z0-9_.-]", "_", local_part)[:40] or "user"
        username = base
        for suffix in range(2, 1000):
            result = await self.db.execute(
                select(User.id).where(User.username == username)
            )
            if result.first() is None:
                return username
            username = f"{base}{suffix}"
        return f"{base}-{uuid.uuid4().hex[:8]}"
