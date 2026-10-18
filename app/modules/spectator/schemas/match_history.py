from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MatchHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tournament_id: int
    match_number: int
    team_a_id: int | None
    team_b_id: int | None
    scheduled_at: datetime
    status: str
    result: dict | None = None