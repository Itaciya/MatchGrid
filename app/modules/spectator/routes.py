
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, func, or_
from sqlalchemy.orm import Session, aliased

from app.data_access.database import get_db
from app.modules.match.models.match import Match
from app.modules.match.models.match_result import MatchResult
from app.modules.match.schemas.fixture import FixtureResponse
from app.modules.player_team.models.player import Player
from app.modules.player_team.models.team import Team
from app.modules.score.models.score import Score, ScoreVerificationStatus
from app.modules.score.schemas.match_result import MatchResultResponse
from app.modules.spectator.schemas.match_history import MatchHistoryResponse
from app.modules.tournament.models.tournament import Tournament
from app.modules.tournament.schemas.tournament import TournamentResponse
from app.modules.tournament_team.models.tournament_team import TournamentTeam


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
        query = query.filter(Tournament.status == tournament_status)

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
    """Expose only results backed by a verified score."""

    result = (
        db.query(MatchResult)
        .join(Match, Match.id == MatchResult.match_id)
        .join(Score, Score.match_id == Match.id)
        .join(Tournament, Tournament.id == Match.tournament_id)
        .filter(
            Match.id == match_id,
            Tournament.fixtures_published.is_(True),
            Match.status == "completed",
            Score.verification_status
            == ScoreVerificationStatus.VERIFIED.value,
            Score.is_verified.is_(True),
        )
        .first()
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verified match result not found",
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
    """Return match history without exposing unverified results."""

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
        verified_data = (
            db.query(MatchResult, Score)
            .join(Score, Score.match_id == MatchResult.match_id)
            .filter(
                MatchResult.match_id == match.id,
                Score.verification_status
                == ScoreVerificationStatus.VERIFIED.value,
                Score.is_verified.is_(True),
            )
            .first()
        )

        result_data = None

        if verified_data is not None:
            result, score = verified_data
            result_data = {
                "outcome": result.outcome,
                "winner_team_id": result.winner_team_id,
                "loser_team_id": result.loser_team_id,
                "team_a_score": score.team_a_score,
                "team_b_score": score.team_b_score,
            }

        history.append(
            {
                "id": match.id,
                "tournament_id": match.tournament_id,
                "match_number": match.match_number,
                "team_a_id": match.team_a_id,
                "team_b_id": match.team_b_id,
                "scheduled_at": match.scheduled_at,
                "status": match.status,
                "result": result_data,
            }
        )

    return history


@router.get("/teams/{team_id}")
def get_public_team_information(
    team_id: int,
    db: Session = Depends(get_db),
):
    """Return public team details, active roster and published tournaments."""

    if team_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="Team ID must be positive",
        )

    team = (
        db.query(Team)
        .filter(
            Team.id == team_id,
            Team.status == "active",
        )
        .first()
    )

    if team is None:
        raise HTTPException(
            status_code=404,
            detail="Public team not found",
        )

    memberships = (
        db.query(TournamentTeam)
        .join(
            Tournament,
            Tournament.id == TournamentTeam.tournament_id,
        )
        .filter(
            TournamentTeam.team_id == team.id,
            Tournament.fixtures_published.is_(True),
        )
        .order_by(Tournament.start_date.desc())
        .all()
    )

    if not memberships:
        raise HTTPException(
            status_code=404,
            detail="Public team not found",
        )

    players = (
        db.query(Player)
        .filter(
            Player.team_id == team.id,
            Player.status == "active",
        )
        .order_by(Player.first_name, Player.last_name)
        .all()
    )

    tournaments = [
        {
            "id": membership.tournament.id,
            "name": membership.tournament.name,
            "status": membership.tournament.status,
            "start_date": membership.tournament.start_date,
            "end_date": membership.tournament.end_date,
        }
        for membership in memberships
    ]

    return {
        "id": team.id,
        "name": team.name,
        "status": team.status,
        "roster": [
            {
                "id": player.id,
                "first_name": player.first_name,
                "last_name": player.last_name,
                "status": player.status,
            }
            for player in players
        ],
        "tournaments": tournaments,
    }


@router.get("/players/{player_id}")
def get_public_player_information(
    player_id: int,
    db: Session = Depends(get_db),
):
    """Return public player profile and performance from verified scores."""

    if player_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="Player ID must be positive",
        )

    player = (
        db.query(Player)
        .filter(
            Player.id == player_id,
            Player.status == "active",
        )
        .first()
    )

    if player is None:
        raise HTTPException(
            status_code=404,
            detail="Public player not found",
        )

    team = None

    if player.team_id is not None:
        team = (
            db.query(Team)
            .filter(
                Team.id == player.team_id,
                Team.status == "active",
            )
            .first()
        )

    memberships = (
        db.query(TournamentTeam)
        .join(
            Tournament,
            Tournament.id == TournamentTeam.tournament_id,
        )
        .filter(
            TournamentTeam.team_id == player.team_id,
            Tournament.fixtures_published.is_(True),
        )
        .order_by(Tournament.start_date.desc())
        .all()
        if player.team_id is not None and team is not None
        else []
    )

    if team is None or not memberships:
        raise HTTPException(
            status_code=404,
            detail="Public player not found",
        )

    performance = {
        "played": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "score_for": 0,
        "score_against": 0,
    }

    verified_matches = (
        db.query(Match, Score)
        .join(Score, Score.match_id == Match.id)
        .join(
            Tournament,
            Tournament.id == Match.tournament_id,
        )
        .filter(
            Match.status == "completed",
            Tournament.fixtures_published.is_(True),
            Score.verification_status
            == ScoreVerificationStatus.VERIFIED.value,
            Score.is_verified.is_(True),
            or_(
                Match.team_a_id == team.id,
                Match.team_b_id == team.id,
            ),
        )
        .all()
    )

    for match, score in verified_matches:
        if match.team_a_id == team.id:
            own_score = score.team_a_score
            opponent_score = score.team_b_score
        else:
            own_score = score.team_b_score
            opponent_score = score.team_a_score

        performance["played"] += 1
        performance["score_for"] += own_score
        performance["score_against"] += opponent_score

        if own_score > opponent_score:
            performance["wins"] += 1
        elif own_score == opponent_score:
            performance["draws"] += 1
        else:
            performance["losses"] += 1

    return {
        "id": player.id,
        "first_name": player.first_name,
        "last_name": player.last_name,
        "team": {
            "id": team.id,
            "name": team.name,
        },
        "tournaments": [
            {
                "id": membership.tournament.id,
                "name": membership.tournament.name,
                "status": membership.tournament.status,
            }
            for membership in memberships
        ],
        "performance": performance,
    }


@router.get("/search")
def search_public_information(
    q: str = Query(min_length=2, max_length=100),
    category: str = Query(
        default="all",
        pattern="^(all|tournaments|teams|players|matches)$",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Search public tournaments, teams, players and matches."""

    term = q.strip()

    if len(term) < 2:
        raise HTTPException(
            status_code=422,
            detail="Search query must contain at least 2 non-space characters",
        )

    pattern = f"%{term}%"
    results = {}

    def paginate(query):
        total = query.count()
        items = (
            query.offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
        }

    if category in ("all", "tournaments"):
        query = (
            db.query(Tournament)
            .filter(
                Tournament.fixtures_published.is_(True),
                Tournament.name.ilike(pattern),
            )
            .order_by(Tournament.start_date, Tournament.id)
        )

        data = paginate(query)
        results["tournaments"] = {
            **data,
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "status": item.status,
                    "start_date": item.start_date,
                    "end_date": item.end_date,
                }
                for item in data["items"]
            ],
        }

    if category in ("all", "teams"):
        query = (
            db.query(Team)
            .join(
                TournamentTeam,
                TournamentTeam.team_id == Team.id,
            )
            .join(
                Tournament,
                Tournament.id == TournamentTeam.tournament_id,
            )
            .filter(
                Team.status == "active",
                Tournament.fixtures_published.is_(True),
                Team.name.ilike(pattern),
            )
            .distinct()
            .order_by(Team.name, Team.id)
        )

        data = paginate(query)
        results["teams"] = {
            **data,
            "items": [
                {"id": item.id, "name": item.name}
                for item in data["items"]
            ],
        }

    if category in ("all", "players"):
        query = (
            db.query(Player)
            .join(Team, Team.id == Player.team_id)
            .join(
                TournamentTeam,
                TournamentTeam.team_id == Team.id,
            )
            .join(
                Tournament,
                Tournament.id == TournamentTeam.tournament_id,
            )
            .filter(
                Player.status == "active",
                Team.status == "active",
                Tournament.fixtures_published.is_(True),
                or_(
                    Player.first_name.ilike(pattern),
                    Player.last_name.ilike(pattern),
                ),
            )
            .distinct()
            .order_by(Player.first_name, Player.last_name, Player.id)
        )

        data = paginate(query)
        results["players"] = {
            **data,
            "items": [
                {
                    "id": item.id,
                    "first_name": item.first_name,
                    "last_name": item.last_name,
                    "team_id": item.team_id,
                }
                for item in data["items"]
            ],
        }

    if category in ("all", "matches"):
        team_a = aliased(Team)
        team_b = aliased(Team)

        query = (
            db.query(Match)
            .join(
                Tournament,
                Tournament.id == Match.tournament_id,
            )
            .outerjoin(team_a, Match.team_a_id == team_a.id)
            .outerjoin(team_b, Match.team_b_id == team_b.id)
            .filter(
                Tournament.fixtures_published.is_(True),
                or_(
                    Tournament.name.ilike(pattern),
                    func.cast(Match.match_number, type_=String).ilike(
                        pattern
                    ),
                    team_a.name.ilike(pattern),
                    team_b.name.ilike(pattern),
                ),
            )
            .order_by(Match.scheduled_at, Match.match_number)
        )

        data = paginate(query)
        results["matches"] = {
            **data,
            "items": [
                {
                    "id": item.id,
                    "tournament_id": item.tournament_id,
                    "match_number": item.match_number,
                    "team_a_id": item.team_a_id,
                    "team_b_id": item.team_b_id,
                    "scheduled_at": item.scheduled_at,
                    "status": item.status,
                }
                for item in data["items"]
            ],
        }

    return {
        "query": term,
        "category": category,
        "results": results,
    }
