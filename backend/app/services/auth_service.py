"""Authentication business logic."""

import asyncio
import logging
import uuid

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import get_password_hash, verify_password, create_access_token

logger = logging.getLogger(__name__)
_google_request = google_requests.Request()


class AuthService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, payload: UserCreate) -> User:
        # Check duplicates
        result = await self.db.execute(
            select(User).where(
                (User.email == payload.email) | (User.username == payload.username)
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email or username already registered",
            )

        user = User(
            id=str(uuid.uuid4()),
            email=payload.email,
            username=payload.username,
            hashed_password=get_password_hash(payload.password),
            full_name=payload.full_name,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def login(self, username: str, password: str) -> dict:
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()

        if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
            )
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is inactive")

        token = create_access_token({"sub": user.id, "username": user.username})
        return {"access_token": token, "token_type": "bearer", "user": user}

    async def google_login(self, credential: str) -> dict:
        """Verify a Google Identity Services credential and log in or sign up the user."""
        try:
            id_info = await asyncio.to_thread(
                google_id_token.verify_oauth2_token,
                credential,
                _google_request,
                settings.GOOGLE_CLIENT_ID,
            )
        except ValueError as e:
            logger.warning(f"Google credential verification failed: {e}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google credential")

        if not id_info.get("email_verified"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google email is not verified")

        google_sub = id_info["sub"]
        email = id_info["email"]

        result = await self.db.execute(select(User).where(User.google_sub == google_sub))
        user = result.scalar_one_or_none()

        if not user:
            result = await self.db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if user:
                # Existing local account signing in with the same verified Google email — link it.
                user.google_sub = google_sub
            else:
                user = User(
                    id=str(uuid.uuid4()),
                    email=email,
                    username=await self._unique_username_from_email(email),
                    hashed_password=None,
                    full_name=id_info.get("name"),
                    auth_provider="google",
                    google_sub=google_sub,
                )
                self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)

        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is inactive")

        token = create_access_token({"sub": user.id, "username": user.username})
        return {"access_token": token, "token_type": "bearer", "user": user}

    async def _unique_username_from_email(self, email: str) -> str:
        base = email.split("@")[0].lower() or "user"
        username = base
        suffix = 1
        while True:
            result = await self.db.execute(select(User).where(User.username == username))
            if result.scalar_one_or_none() is None:
                return username
            suffix += 1
            username = f"{base}{suffix}"
