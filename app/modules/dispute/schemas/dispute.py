from typing import Annotated, Literal
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


MatchId = Annotated[int, Field(ge=1, strict=True)]


class DisputeCreate(BaseModel):
    """Schema for submitting a dispute for a match."""

    model_config = ConfigDict(extra="forbid")

    match_id: MatchId
    reason: str = Field(min_length=1, max_length=5000)


class DisputeUpdate(BaseModel):
    """Schema for updating dispute information."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(
        default=None,
        min_length=1,
        max_length=5000,
    )
    status: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    resolution: str | None = Field(
        default=None,
        min_length=1,
        max_length=5000,
    )

    @model_validator(mode="after")
    def check_at_least_one_field(self):
        if all(
            value is None
            for value in (
                self.reason,
                self.status,
                self.resolution,
            )
        ):
            raise ValueError(
                "At least one field must be provided for an update"
            )

        return self


class DisputeStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "pending",
        "under_review",
        "resolved",
        "rejected",
    ]

class DisputeResponse(BaseModel):
    """Schema for returning dispute data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    user_id: int
    reason: str
    status: str
    resolution: str | None = None
    created_at: datetime
    updated_at: datetime
