from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.data_access.database import get_db
from app.modules.player_team.models.player import Player
from app.modules.tournament_team.schemas.roster import (
    TournamentRosterPlayerAdd,
    TournamentRosterPlayerResponse,
)
from app.modules.tournament_team.services.roster_service import (
    add_player_to_tournament_roster,
    get_tournament_roster,
    remove_player_from_tournament_roster,
    search_tournament_players,
)
from app.modules.user.models import User


router = APIRouter(
    prefix="/tournament-rosters",
    tags=["Tournament Player Roster"],
)


@router.get(
    "/{tournament_id}/teams/{team_id}",
    response_model=list[TournamentRosterPlayerResponse],
)
def read_tournament_roster(
    tournament_id: int,
    team_id: int,
    current_user: User = Depends(require_role("player", "captain")),
    db: Session = Depends(get_db),
):
    return get_tournament_roster(
        db,
        tournament_id,
        team_id,
        current_user.id,
    )


@router.get(
    "/{tournament_id}/teams/{team_id}/search",
    response_model=list[TournamentRosterPlayerResponse],
)
def search_players_for_tournament(
    tournament_id: int,
    team_id: int,
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(require_role("player", "captain")),
    db: Session = Depends(get_db),
):
    return search_tournament_players(
        db,
        tournament_id,
        team_id,
        current_user.id,
        q,
        limit,
    )


@router.post(
    "/{tournament_id}/teams/{team_id}",
    response_model=TournamentRosterPlayerResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_player_to_roster(
    tournament_id: int,
    team_id: int,
    data: TournamentRosterPlayerAdd,
    current_user: User = Depends(require_role("player", "captain")),
    db: Session = Depends(get_db),
):
    add_player_to_tournament_roster(
        db,
        tournament_id,
        team_id,
        data.player_id,
        current_user.id,
    )

    player = (
        db.query(Player)
        .filter(Player.id == data.player_id)
        .first()
    )

    return player


@router.delete(
    "/{tournament_id}/teams/{team_id}/{player_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_player_from_roster(
    tournament_id: int,
    team_id: int,
    player_id: int,
    current_user: User = Depends(require_role("player", "captain")),
    db: Session = Depends(get_db),
):
    remove_player_from_tournament_roster(
        db,
        tournament_id,
        team_id,
        player_id,
        current_user.id,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
