from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.data_access.database import get_db
from app.modules.player_team.schemas.player import PlayerCreate, PlayerResponse
from app.modules.player_team.services.player_service import (
    create_player,
    get_player,
)
from app.modules.user.models import User


router = APIRouter(
    prefix="/player-team",
    tags=["Player & Team"],
)


@router.get("/")
def player_team_home():
    return {"message": "Player & Team router is working"}


@router.post(
    "/profile",
    response_model=PlayerResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_player_profile(
    data: PlayerCreate,
    current_user: User = Depends(require_role("player")),
    db: Session = Depends(get_db),
):
    return create_player(db, current_user.id, data)


@router.get(
    "/profile/{player_id}",
    response_model=PlayerResponse,
)
def get_player_profile(
    player_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_player(db, player_id)