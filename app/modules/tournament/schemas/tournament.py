from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RoundRobinConfig(BaseModel):
    """Configuration required for round-robin tournaments."""

    number_of_teams: int = Field(ge=2)


class SingleEliminationConfig(BaseModel):
    """Configuration required for single-elimination tournaments."""

    number_of_teams: int = Field(ge=2)


class TournamentCreate(BaseModel):
    """Schema for creating a tournament. organizer_id is never client-supplied --
    it comes from the authenticated user, to prevent spoofing ownership."""

    name: str = Field(min_length=3, max_length=150)
    description: str | None = None
    format: str = Field(min_length=1, max_length=50)
    format_config: (
        RoundRobinConfig | SingleEliminationConfig | None
    ) = None
    start_date: datetime
    end_date: datetime

    @model_validator(mode="after")
    def check_dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class TournamentUpdate(BaseModel):
    """Schema for updating a tournament. All fields optional (partial update)."""

    name: str | None = Field(default=None, min_length=3, max_length=150)
    description: str | None = None
    format: str | None = Field(default=None, min_length=1, max_length=50)
    format_config: (
        RoundRobinConfig | SingleEliminationConfig | None
    ) = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str | None = Field(default=None, min_length=1, max_length=50)

    @model_validator(mode="after")
    def check_dates(self):
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class TournamentResponse(BaseModel):
    """Schema for returning tournament data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    format: str
    format_config: (
        RoundRobinConfig | SingleEliminationConfig | None
    )
    start_date: datetime
    end_date: datetime
    status: str
    organizer_id: int
    created_at: datetime
    updated_at: datetime