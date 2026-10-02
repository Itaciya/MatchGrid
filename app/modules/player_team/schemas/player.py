from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.player_team.models.player import PlayerStatus


def validate_player_name(value: str) -> str:
    """Validate and normalize a player name."""

    value = value.strip()

    if not value:
        raise ValueError("Name cannot be empty")

    if not all(
        character.isalpha() or character in " -'"
        for character in value
    ):
        raise ValueError(
            "Name can contain only letters, spaces, hyphens, and apostrophes"
        )

    return value


class PlayerCreate(BaseModel):
    """Schema for creating a player profile."""

    team_id: int | None = Field(default=None, gt=0)

    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, value: str) -> str:
        return validate_player_name(value)


class PlayerUpdate(BaseModel):
    """Schema for updating a player profile. All fields are optional."""

    team_id: int | None = Field(default=None, gt=0)

    first_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    last_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    status: PlayerStatus | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_names(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return validate_player_name(value)


class PlayerStatusUpdate(BaseModel):
    """Schema for updating a player's eligibility status."""

    status: PlayerStatus


class PlayerResponse(BaseModel):
    """Schema for returning player data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    team_id: int | None
    first_name: str
    last_name: str
    status: PlayerStatus
    created_at: datetime
    updated_at: datetime