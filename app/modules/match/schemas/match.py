from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MatchStatusResponse(BaseModel):
    """Schema for returning a match's status after a status change."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tournament_id: int
    match_number: int
    team_a_id: int | None
    team_b_id: int | None
    status: str
    scheduled_at: datetime
    started_at: datetime | None
