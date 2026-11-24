from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

UserRole = Literal["organiser", "player", "scorer", "spectator", "official"]

# Roles a new account can sign up with. Organisers pick scorers for their own
# tournaments; the separate referee ("official") role is no longer offered,
# though existing official accounts keep working.
RegisterRole = Literal["organiser", "player", "scorer", "spectator"]


def _normalize_email(email: str) -> str:
    return email.strip().lower()


class UserRegister(BaseModel):
    """Schema for registering a new user."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: RegisterRole

    @field_validator("email")
    @classmethod
    def normalize_email(cls, email: str) -> str:
        return _normalize_email(email)

    @field_validator("password")
    @classmethod
    def validate_password_policy(cls, password: str) -> str:
        """Require a password containing letters and numbers."""
        if not any(char.isalpha() for char in password):
            raise ValueError("Password must contain at least one letter")

        if not any(char.isdigit() for char in password):
            raise ValueError("Password must contain at least one number")

        weak_passwords = {
            "password",
            "password123",
            "12345678",
            "qwerty123",
            "admin123",
        }

        if password.lower() in weak_passwords:
            raise ValueError("This password is too common")

        return password


class UserLogin(BaseModel):
    """Schema for authenticating an existing user."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, email: str) -> str:
        return _normalize_email(email)


class RefreshRequest(BaseModel):
    """Schema for exchanging a refresh token for a new token pair."""

    refresh_token: str = Field(min_length=1, max_length=2048)


class UserResponse(BaseModel):
    """Schema for returning user data. Never includes password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """Schema for returning authentication tokens after login."""

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


