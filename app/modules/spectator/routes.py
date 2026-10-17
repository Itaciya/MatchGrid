from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.data_access.database import get_db
from app.modules.match.models.match import Match
from app.modules.match.models.match_result import MatchResult
from app.modules.match.schemas.fixture import FixtureResponse
from app.modules.score.schemas.match_result import MatchResultResponse
from app.modules.tournament.models.tournament import Tournament
from app.modules.tournament.schemas.tournament import TournamentResponse


router = APIRouter(
    prefix="/spectator",
    tags=["Spectator"],
)


def _get_published_tournament(
    db: Session,
    tournament_id: int,
) -> Tournament:
    """Return a tournament only when its fixtures are published."""

    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == tournament_id)
        .first()
    )

    if tournament is None or not tournament.fixtures_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tournament not found",
        )

    return tournament


@router.get("/")
def spectator_home():
    return {"message": "Spectator router is working"}


# SCRUM-187: Public tournament list
@router.get(
    "/tournaments",
    response_model=list[TournamentResponse],
)
def list_public_tournaments(
    tournament_status: str | None = Query(
        default=None,
        alias="status",
        min_length=1,
    ),
    db: Session = Depends(get_db),
):
    """List tournaments without requiring authentication."""

    query = db.query(Tournament)

    if tournament_status is not None:
        query = query.filter(
            Tournament.status == tournament_status
        )

    return query.order_by(
        Tournament.start_date.asc(),
        Tournament.id.asc(),
    ).all()


# SCRUM-188: Public tournament details
@router.get(
    "/tournaments/{tournament_id}",
    response_model=TournamentResponse,
)
def get_public_tournament_details(
    tournament_id: int,
    db: Session = Depends(get_db),
):
    """Return the details of a tournament."""

    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == tournament_id)
        .first()
    )

    if tournament is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tournament not found",
        )

    return tournament


# SCRUM-189: Public fixtures
@router.get(
    "/tournaments/{tournament_id}/fixtures",
    response_model=list[FixtureResponse],
)
def list_public_fixtures(
    tournament_id: int,
    db: Session = Depends(get_db),
):
    """List fixtures only after the tournament publishes them."""

    _get_published_tournament(db, tournament_id)

    return (
        db.query(Match)
        .filter(Match.tournament_id == tournament_id)
        .order_by(
            Match.scheduled_at.asc(),
            Match.match_number.asc(),
        )
        .all()
    )


# SCRUM-190: Public finalized match result
@router.get(
    "/matches/{match_id}/result",
    response_model=MatchResultResponse,
)
def get_public_match_result(
    match_id: int,
    db: Session = Depends(get_db),
):
    """Return the official result of a published tournament match."""

    result = (
        db.query(MatchResult)
        .join(Match, Match.id == MatchResult.match_id)
        .join(
            Tournament,
            Tournament.id == Match.tournament_id,
        )
        .filter(
            Match.id == match_id,
            Tournament.fixtures_published.is_(True),
        )
        .first()
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match result not found",
        )

    return result