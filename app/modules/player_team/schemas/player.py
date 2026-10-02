from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlayerCreate(BaseModel):
    """Schema for creating a player profile."""

    team_id: int = Field(gt=0)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class PlayerUpdate(BaseModel):
    """Schema for updating a player profile. All fields are optional."""

    team_id: int | None = Field(default=None, gt=0)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None


class PlayerResponse(BaseModel):
    """Schema for returning player data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    team_id: int
    first_name: str
    last_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
