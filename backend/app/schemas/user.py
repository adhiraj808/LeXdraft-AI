from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

USERNAME_PATTERN = r"^[A-Za-z0-9_.-]+$"
MAX_PASSWORD_BYTES = 72  # bcrypt ignores everything after the 72nd byte


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=USERNAME_PATTERN)
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=200)

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        # Emails are matched case-insensitively everywhere (register, Google link-up).
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(
                f"Password must be at most {MAX_PASSWORD_BYTES} bytes long"
            )
        return value

    @field_validator("full_name")
    @classmethod
    def clean_full_name(cls, value: Optional[str]) -> Optional[str]:
        value = (value or "").strip()
        return value or None


class UserLogin(BaseModel):
    # Deliberately no pattern / minimum length: accounts created before the
    # stricter signup rules must still be able to log in.
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class GoogleAuthRequest(BaseModel):
    credential: str = Field(min_length=10, max_length=8192)


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
