"""Unit tests for business logic services."""

import pytest
from app.services.auth_service import AuthService
from app.schemas.user import UserCreate


@pytest.mark.asyncio
async def test_register_new_user(db_session):
    service = AuthService(db_session)
    payload = UserCreate(
        email="new@example.com",
        username="newuser",
        password="securepassword123",
        full_name="New User",
    )
    user = await service.register(payload)
    assert user.email == payload.email
    assert user.username == payload.username
    assert user.hashed_password != payload.password  # must be hashed


@pytest.mark.asyncio
async def test_register_duplicate_user(db_session):
    from fastapi import HTTPException
    service = AuthService(db_session)
    payload = UserCreate(email="dup@example.com", username="dupuser", password="pass1234")
    await service.register(payload)

    with pytest.raises(HTTPException) as exc:
        await service.register(payload)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_login_wrong_password(db_session):
    from fastapi import HTTPException
    service = AuthService(db_session)
    payload = UserCreate(email="login@example.com", username="loginuser", password="correctpass")
    await service.register(payload)

    with pytest.raises(HTTPException) as exc:
        await service.login("loginuser", "wrongpass")
    assert exc.value.status_code == 401
