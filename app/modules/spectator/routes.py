from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.data_access.database import get_db
from app.modules.match.models.match import Match
from app.modules.match.models.match_result import MatchResult
from app.modules.match.schemas.fixture import FixtureResponse
from app.modules.score.schemas.match_result import MatchResultResponse
from app.modules.tournament.models.tournament import Tournament
from app.modules.tournament.schemas.tournament import TournamentResponse
from app.modules.spectator.schemas.match_history import MatchHistoryResponse

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


@router.get(
    "/tournaments/{tournament_id}/history",
    response_model=list[MatchHistoryResponse],
)
def get_public_match_history(
    tournament_id: int,
    db: Session = Depends(get_db),
):
    """Return chronological match history for a published tournament."""

    _get_published_tournament(db, tournament_id)

    matches = (
        db.query(Match)
        .filter(Match.tournament_id == tournament_id)
        .order_by(
            Match.scheduled_at.asc(),
            Match.match_number.asc(),
        )
        .all()
    )

    history = []

    for match in matches:
        result = (
            db.query(MatchResult)
            .filter(MatchResult.match_id == match.id)
            .first()
        )

        history.append(
            {
                "id": match.id,
                "tournament_id": match.tournament_id,
                "match_number": match.match_number,
                "team_a_id": match.team_a_id,
                "team_b_id": match.team_b_id,
                "scheduled_at": match.scheduled_at,
                "status": match.status,
                "result": (
                    {
                        "outcome": result.outcome,
                        "winner_team_id": result.winner_team_id,
                        "loser_team_id": result.loser_team_id,
                        "team_a_score": result.team_a_score,
                        "team_b_score": result.team_b_score,
                    }
                    if result is not None
                    else None
                ),
            }
        )

    return history