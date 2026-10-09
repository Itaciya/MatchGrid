from typing import Annotated, Literal
from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

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

class DisputeMatchInfo(BaseModel):
    """Match information included in an organizer's dispute review."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    match_number: int
    scheduled_at: datetime
    status: str
    team_a_id: int
    team_b_id: int
    team_a_name: str
    team_b_name: str

class DisputeResultInfo(BaseModel):
    """Score information associated with a disputed match."""

    model_config = ConfigDict(from_attributes=True)

    team_a_score: int
    team_b_score: int
    verification_status: str


class OrganizerDisputeReviewResponse(DisputeResponse):
    """Dispute details with the related match and optional result."""

    match: DisputeMatchInfo
    result: DisputeResultInfo | None = None

class DisputeResolutionRequest(BaseModel):
    """Request body for an organizer's dispute resolution decision."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["resolved", "rejected"]
    resolution: str = Field(min_length=1, max_length=5000)

    corrected_team_a_score: int | None = Field(
        default=None,
        ge=0,
        strict=True,
    )
    corrected_team_b_score: int | None = Field(
        default=None,
        ge=0,
        strict=True,
    )

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Resolution details cannot be empty")

        return value

    @model_validator(mode="after")
    def validate_score_correction(self):
        has_team_a_score = self.corrected_team_a_score is not None
        has_team_b_score = self.corrected_team_b_score is not None

        if has_team_a_score != has_team_b_score:
            raise ValueError(
                "Both corrected team scores must be provided together"
            )

        if (
            self.decision == "rejected"
            and (has_team_a_score or has_team_b_score)
        ):
            raise ValueError(
                "Scores can only be corrected when a dispute is resolved"
            )

        return self