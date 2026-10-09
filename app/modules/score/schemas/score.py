from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

# strict=True: reject "3", 2.5 and True instead of silently coercing them.
ScoreValue = Annotated[int, Field(ge=0, strict=True)]
MatchId = Annotated[int, Field(ge=1, strict=True)]


class ScoreCreate(BaseModel):
    """Schema for submitting a score for a match.

    is_verified is deliberately absent: verification is a separate,
    organiser-controlled step, never set by the submitter.
    """

    model_config = ConfigDict(extra="forbid")

    match_id: MatchId
    team_a_score: ScoreValue
    team_b_score: ScoreValue


class ScoreUpdate(BaseModel):
    """Schema for updating a score. Partial update, but at least one
    score value must be provided. Services should apply it with
    model_dump(exclude_none=True)."""

    model_config = ConfigDict(extra="forbid")

    team_a_score: ScoreValue | None = None
    team_b_score: ScoreValue | None = None

    @model_validator(mode="after")
    def check_at_least_one_score(self):
        if self.team_a_score is None and self.team_b_score is None:
            raise ValueError(
                "at least one of team_a_score or team_b_score must be provided"
            )
        return self


class ScoreResponse(BaseModel):
    """Schema for returning score data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    team_a_score: int
    team_b_score: int
    is_verified: bool
    created_at: datetime
    updated_at: datetime
