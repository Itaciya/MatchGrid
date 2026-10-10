from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MatchResultResponse(BaseModel):
    """The official result of a finalized match."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    outcome: str
    winner_team_id: int | None
    loser_team_id: int | None
    team_a_score: int
    team_b_score: int
    finalized_by_id: int
    finalized_at: datetime
    created_at: datetime
    updated_at: datetime
