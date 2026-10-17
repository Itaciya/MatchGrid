
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


UserId = Annotated[int, Field(ge=1, strict=True)]


class NotificationCreate(BaseModel):
    """Schema for creating a notification."""

    model_config = ConfigDict(extra="forbid")

    user_id: UserId
    notification_type: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1)


    @field_validator("notification_type", "content")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("This field cannot be empty or whitespace")

        return value


class NotificationUpdate(BaseModel):
    """Schema for updating notification information."""

    model_config = ConfigDict(extra="forbid")

    notification_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    content: str | None = Field(default=None, min_length=1)
    is_read: bool | None = None

    @field_validator("notification_type", "content")
    @classmethod
    def validate_non_empty_text(cls, value: str | None) -> str | None:
        if value is None:
            return value

        value = value.strip()

        if not value:
            raise ValueError("This field cannot be empty or whitespace")

        return value


class NotificationReadStatusUpdate(BaseModel):
    """Schema for updating notification read status."""

    model_config = ConfigDict(extra="forbid")

    is_read: bool


class NotificationResponse(BaseModel):
    """Schema for returning notification data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    notification_type: str
    content: str
    is_read: bool
    created_at: datetime
    updated_at: datetime
