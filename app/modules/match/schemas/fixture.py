from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FixtureCreate(BaseModel):
    """Schema for creating round-robin fixtures."""

    tournament_id: int = Field(gt=0)
    team_ids: list[int] = Field(min_length=2)
    venue_id: int = Field(gt=0)
    fixture_date: date
    fixture_time: time

    @model_validator(mode="after")
    def validate_teams(self):
        if len(self.team_ids) != len(set(self.team_ids)):
            raise ValueError("team_ids must not contain duplicates")

        if any(team_id <= 0 for team_id in self.team_ids):
            raise ValueError("team_ids must contain only positive IDs")

        return self


class FixtureUpdate(BaseModel):
    """Schema for updating a fixture's schedule or venue."""

    scheduled_at: datetime | None = None
    venue_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_update_fields(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")

        if "scheduled_at" in self.model_fields_set:
            if self.scheduled_at is None:
                raise ValueError("scheduled_at cannot be null")

        return self


class FixtureResponse(BaseModel):
    """Schema for returning a match fixture."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tournament_id: int
    match_number: int
    round_id: int | None = None
    team_a_id: int | None
    team_b_id: int | None
    venue_id: int | None
    scheduled_at: datetime
    status: str
    created_at: datetime
    updated_at: datetime