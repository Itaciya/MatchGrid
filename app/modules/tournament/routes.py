
from fastapi import APIRouter, Depends, HTTPException, Query,status
from sqlalchemy.orm import Session
from app.modules.tournament.services.standings_service import (
    calculate_tournament_standings,
)
from app.data_access.database import get_db
from app.modules.tournament.schemas.tournament import TournamentResponse
from app.modules.tournament.services.tournament_service import (
    get_tournament_by_id,
    list_tournaments,
)


router = APIRouter(
    prefix="/tournaments",
    tags=["Tournament"],
)


@router.get(
    "/",
    response_model=list[TournamentResponse],
)
def get_tournaments(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return list_tournaments(
        db,
        status=status,
    )


@router.get(
    "/{tournament_id}",
    response_model=TournamentResponse,
)
def get_tournament_details(
    tournament_id: int,
    db: Session = Depends(get_db),
):
    tournament = get_tournament_by_id(
        db,
        tournament_id,
    )

    if tournament is None:
        raise HTTPException(
            status_code=404,
            detail="Tournament not found",
        )

    return tournament
@router.get(
    "/{tournament_id}/standings",
    status_code=status.HTTP_200_OK,
)
def get_tournament_standings_endpoint(
    tournament_id: int,
    db: Session = Depends(get_db),
):
    """Return standings calculated from official match results."""

    return calculate_tournament_standings(
        db=db,
        tournament_id=tournament_id,
    )