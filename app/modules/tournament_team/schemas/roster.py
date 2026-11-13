from pydantic import BaseModel, ConfigDict, Field


class TournamentRosterPlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: int = Field(validation_alias="id")
    user_id: int
    first_name: str
    last_name: str
    status: str


class TournamentRosterPlayerAdd(BaseModel):
    player_id: int = Field(gt=0)
