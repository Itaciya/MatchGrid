from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class OfficialAssignmentCreate(BaseModel):
    official_id: int
    assignment_type: Literal["referee", "scorer"]


class OfficialAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    official_id: int
    assignment_type: str
    status: str
    created_at: datetime


class AssignedMatchResponse(BaseModel):
    id: int
    tournament_id: int
    match_number: int
    team_a_id: int | None
    team_b_id: int | None
    venue_id: int | None
    scheduled_at: datetime
    status: str
    assignment_type: str