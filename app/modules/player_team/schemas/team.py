from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.player_team.models.team import TeamStatus
from app.modules.player_team.schemas.player import PlayerResponse


class TeamCreate(BaseModel):
    """Schema for creating a team."""

    name: str = Field(min_length=1, max_length=100)
    captain_id: int = Field(gt=0)


class TeamUpdate(BaseModel):
    """Schema for updating a team. All fields are optional."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    captain_id: int | None = Field(default=None, gt=0)
    status: TeamStatus | None = None

class TeamStatusUpdate(BaseModel):
    """Schema for updating team status."""

    status: TeamStatus

class TeamResponse(BaseModel):
    """Schema for returning team data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    captain_id: int
    status: TeamStatus
    created_at: datetime
    updated_at: datetime
    players: list[PlayerResponse] = Field(default_factory=list)