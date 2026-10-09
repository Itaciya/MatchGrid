from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.modules.match.models.match import Match
from app.modules.score.models.score import Score, ScoreVerificationStatus
from app.modules.tournament.models.tournament import Tournament
from app.modules.tournament_team.models.tournament_team import TournamentTeam


def calculate_tournament_standings(
    db: Session,
    tournament_id: int,
) -> list[dict]:
    """
    Calculate standings from completed matches with verified scores.

    Standings are calculated when requested instead of being stored
    separately. Therefore, approved score corrections are reflected
    automatically in the next standings response.

    Default scoring: win = 3 points, draw = 1 point, loss = 0 points.
    """

    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == tournament_id)
        .first()
    )

    if tournament is None:
        raise NotFoundException(detail="Tournament not found")

    # Include all registered teams, even if they have not played yet.
    memberships = (
        db.query(TournamentTeam)
        .filter(TournamentTeam.tournament_id == tournament_id)
        .all()
    )

    standings = {}

    for membership in memberships:
        team = membership.team

        standings[membership.team_id] = {
            "team_id": membership.team_id,
            "team_name": team.name,
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "score_for": 0,
            "score_against": 0,
            "score_difference": 0,
            "points": 0,
        }

    # Only official results count toward the standings.
    official_matches = (
        db.query(Match, Score)
        .join(Score, Score.match_id == Match.id)
        .filter(
            Match.tournament_id == tournament_id,
            Match.status == "completed",
            Score.verification_status
            == ScoreVerificationStatus.VERIFIED.value,
            Score.is_verified.is_(True),
        )
        .all()
    )

    for match, score in official_matches:
        team_a_id = match.team_a_id
        team_b_id = match.team_b_id

        # Ignore matches whose teams are not registered in this tournament.
        if (
            team_a_id not in standings
            or team_b_id not in standings
        ):
            continue

        team_a_score = score.team_a_score
        team_b_score = score.team_b_score

        if team_a_score is None or team_b_score is None:
            continue

        team_a_score = int(team_a_score)
        team_b_score = int(team_b_score)

        team_a = standings[team_a_id]
        team_b = standings[team_b_id]

        team_a["played"] += 1
        team_b["played"] += 1

        team_a["score_for"] += team_a_score
        team_a["score_against"] += team_b_score

        team_b["score_for"] += team_b_score
        team_b["score_against"] += team_a_score

        if team_a_score > team_b_score:
            team_a["wins"] += 1
            team_b["losses"] += 1
            team_a["points"] += 3

        elif team_b_score > team_a_score:
            team_b["wins"] += 1
            team_a["losses"] += 1
            team_b["points"] += 3

        else:
            team_a["draws"] += 1
            team_b["draws"] += 1
            team_a["points"] += 1
            team_b["points"] += 1

    result = list(standings.values())

    for row in result:
        row["score_difference"] = (
            row["score_for"] - row["score_against"]
        )

    # Sort by points, score difference, then total score.
    result.sort(
        key=lambda row: (
            -row["points"],
            -row["score_difference"],
            -row["score_for"],
            row["team_name"].lower(),
        )
    )

    for rank, row in enumerate(result, start=1):
        row["rank"] = rank

    return result