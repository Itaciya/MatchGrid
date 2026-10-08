from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VenueCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=150,
    )

    location: str = Field(
        min_length=1,
        max_length=255,
    )

    description: str | None = None

    capacity: int = Field(
        gt=0,
    )


class VenueUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )

    location: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    description: str | None = None

    capacity: int | None = Field(
        default=None,
        gt=0,
    )


class VenueResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    name: str
    location: str
    description: str | None
    capacity: int
    created_at: datetime
    updated_at: datetime