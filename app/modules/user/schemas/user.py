from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

UserRole = Literal["organiser", "player", "scorer", "spectator", "official"]


class UserRegister(BaseModel):
    """Schema for registering a new user."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: UserRole


class UserLogin(BaseModel):
    """Schema for authenticating an existing user."""

    email: EmailStr
    password: str


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
