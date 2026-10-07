from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FixtureCreate(BaseModel):
    """Schema for creating a fixture."""

    tournament_id: int = Field(gt=0)
    participant_ids: list[int] = Field(min_length=2)
    format: str = Field(min_length=1, max_length=50)
    fixture_date: date
    fixture_time: time
    venue: str = Field(min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_participants(self):
        if len(self.participant_ids) != len(set(self.participant_ids)):
            raise ValueError(
                "participant_ids must not contain duplicates"
            )

        if any(participant_id <= 0 for participant_id in self.participant_ids):
            raise ValueError(
                "participant_ids must contain only positive IDs"
            )

        return self


class FixtureResponse(BaseModel):
    """Schema for returning fixture data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tournament_id: int
    participant_ids: list[int]
    format: str
    fixture_date: date
    fixture_time: time
    venue: str
    status: str
    created_at: datetime
    updated_at: datetime
