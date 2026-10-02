from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.core.exceptions import ForbiddenException
from app.data_access.database import get_db

from app.modules.player_team.schemas.player import (
    PlayerCreate,
    PlayerResponse,
    PlayerStatusUpdate,
    PlayerUpdate,
)
from app.modules.player_team.schemas.team import (
    TeamResponse,
    TeamStatusUpdate,
)

from app.modules.player_team.services.player_service import (
    add_player_to_team,
    create_player,
    get_player,
    remove_player_from_team,
    update_player_profile,
    update_player_status,
)
from app.modules.player_team.services.team_service import (
    get_team,
    update_team_status,
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


@router.patch(
    "/profile/{player_id}",
    response_model=PlayerResponse,
)
def update_player_profile_endpoint(
    player_id: int,
    data: PlayerUpdate,
    current_user: User = Depends(require_role("player")),
    db: Session = Depends(get_db),
):
    player = get_player(db, player_id)

    if player.user_id != current_user.id:
        raise ForbiddenException(
            detail="You can only update your own profile"
        )

    return update_player_profile(db, player_id, data)


@router.patch(
    "/profile/{player_id}/status",
    response_model=PlayerResponse,
)
def update_player_profile_status(
    player_id: int,
    data: PlayerStatusUpdate,
    current_user: User = Depends(require_role("organiser")),
    db: Session = Depends(get_db),
):
    return update_player_status(db, player_id, data)


@router.get(
    "/team/{team_id}",
    response_model=TeamResponse,
)
def get_team_details(
    team_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_team(db, team_id)


@router.patch(
    "/team/{team_id}/status",
    response_model=TeamResponse,
)
def update_team_status_endpoint(
    team_id: int,
    data: TeamStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    team = get_team(db, team_id)

    if team.captain_id != current_user.id:
        raise ForbiddenException(
            detail="Only the team captain can update team status"
        )

    return update_team_status(
        db,
        team_id,
        data.status,
    )


@router.post(
    "/team/{team_id}/players/{player_id}",
    response_model=PlayerResponse,
    status_code=status.HTTP_200_OK,
)
def add_player_to_team_endpoint(
    team_id: int,
    player_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return add_player_to_team(
        db,
        team_id,
        player_id,
        current_user.id,
    )

@router.delete(
    "/team/{team_id}/players/{player_id}",
    response_model=PlayerResponse,
)
def remove_player_from_team_endpoint(
    team_id: int,
    player_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return remove_player_from_team(
        db,
        team_id,
        player_id,
        current_user.id,
    )