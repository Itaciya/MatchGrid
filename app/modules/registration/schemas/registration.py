from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RegistrationType(str, Enum):
    TEAM = "team"
    PLAYER = "player"


class RegistrationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RegistrationCreate(BaseModel):
    """Schema for creating a registration request."""

    tournament_id: int = Field(gt=0)
    team_id: int | None = Field(default=None, gt=0)
    player_id: int | None = Field(default=None, gt=0)
    registration_type: RegistrationType
    note: str | None = None

    @model_validator(mode="after")
    def validate_participant(self):
        if self.registration_type == RegistrationType.TEAM:
            if self.team_id is None:
                raise ValueError("team_id is required for team registration")

            if self.player_id is not None:
                raise ValueError(
                    "player_id must not be provided for team registration"
                )

        elif self.registration_type == RegistrationType.PLAYER:
            if self.player_id is None:
                raise ValueError("player_id is required for player registration")

            if self.team_id is not None:
                raise ValueError(
                    "team_id must not be provided for player registration"
                )

        return self


class RegistrationUpdate(BaseModel):
    """Schema for updating editable registration information."""

    note: str | None = None


class RegistrationResponse(BaseModel):
    """Schema for returning registration data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tournament_id: int
    team_id: int | None
    player_id: int | None
    registration_type: RegistrationType
    status: RegistrationStatus
    registered_at: datetime
    reviewed_at: datetime | None
    note: str | None
    