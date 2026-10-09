from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BadRequestException, NotFoundException
from app.modules.match.models.match import Match
from app.modules.score.models.score import (
    Score,
    ScoreVerificationStatus,
)
from app.modules.tournament.models.tournament import Tournament
from app.modules.tournament_team.models.tournament_team import TournamentTeam


WIN_POINTS = 3
DRAW_POINTS = 1
LOSS_POINTS = 0


def calculate_tournament_standings(
    db: Session,
    tournament_id: int,
) -> list[dict]:
    """
    Calculate tournament standings from official match results.

    Only completed matches with verified scores are counted.
    Unverified, incomplete, missing, or invalid results are ignored.

    Scoring rules are read from tournament.format_config:
        points_per_win  (default: 3)
        points_per_draw (default: 1)
        points_per_loss (default: 0)

    Ranking order:
        1. Points, descending
        2. Score difference, descending
        3. Total score for, descending
        4. Team name, alphabetical
        5. Team ID, ascending

    Standings are calculated on demand. Approved score corrections
    are reflected in the next calculation.
    """

    # Find tournament.
    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == tournament_id)
        .first()
    )

    if tournament is None:
        raise NotFoundException(detail="Tournament not found")

    # Read configurable scoring rules, using defaults when unspecified.
    scoring_config = tournament.format_config or {}

    if not isinstance(scoring_config, dict):
        raise BadRequestException(
            detail="Invalid tournament scoring configuration"
        )

    points_per_win = scoring_config.get(
        "points_per_win", WIN_POINTS
    )
    points_per_draw = scoring_config.get(
        "points_per_draw", DRAW_POINTS
    )
    points_per_loss = scoring_config.get(
        "points_per_loss", LOSS_POINTS
    )

    scoring_rules = {
        "points_per_win": points_per_win,
        "points_per_draw": points_per_draw,
        "points_per_loss": points_per_loss,
    }

    for rule_name, rule_value in scoring_rules.items():
        if (
            not isinstance(rule_value, int)
            or isinstance(rule_value, bool)
            or rule_value < 0
        ):
            raise BadRequestException(
                detail=(
                    f"Invalid scoring rule '{rule_name}'. "
                    "Expected a non-negative integer."
                )
            )

    # Load registered teams and their team data efficiently.
    memberships = (
        db.query(TournamentTeam)
        .options(selectinload(TournamentTeam.team))
        .filter(TournamentTeam.tournament_id == tournament_id)
        .all()
    )

    standings: dict[int, dict] = {}

    for membership in memberships:
        team = membership.team

        if team is None:
            continue

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

    # Only completed matches with verified official scores count.
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

    # Process each eligible match.
    for match, score in official_matches:
        team_a_id = match.team_a_id
        team_b_id = match.team_b_id

        # Ignore matches with missing, duplicate, or unregistered teams.
        if (
            team_a_id is None
            or team_b_id is None
            or team_a_id == team_b_id
            or team_a_id not in standings
            or team_b_id not in standings
        ):
            continue

        team_a_score = score.team_a_score
        team_b_score = score.team_b_score

        # Ignore missing or non-integer scores.
        if (
            not isinstance(team_a_score, int)
            or isinstance(team_a_score, bool)
            or not isinstance(team_b_score, int)
            or isinstance(team_b_score, bool)
        ):
            continue

        # Ignore invalid negative scores.
        if team_a_score < 0 or team_b_score < 0:
            continue

        team_a = standings[team_a_id]
        team_b = standings[team_b_id]

        # Update cumulative match and score statistics.
        team_a["played"] += 1
        team_b["played"] += 1

        team_a["score_for"] += team_a_score
        team_a["score_against"] += team_b_score

        team_b["score_for"] += team_b_score
        team_b["score_against"] += team_a_score

        # Apply the tournament's configured scoring rules.
        if team_a_score > team_b_score:
            team_a["wins"] += 1
            team_b["losses"] += 1

            team_a["points"] += points_per_win
            team_b["points"] += points_per_loss

        elif team_b_score > team_a_score:
            team_b["wins"] += 1
            team_a["losses"] += 1

            team_b["points"] += points_per_win
            team_a["points"] += points_per_loss

        else:
            team_a["draws"] += 1
            team_b["draws"] += 1

            team_a["points"] += points_per_draw
            team_b["points"] += points_per_draw

    # Calculate score difference for every registered team.
    result = list(standings.values())

    for row in result:
        row["score_difference"] = (
            row["score_for"] - row["score_against"]
        )

    # Sort using the ranking and tie-break rules.
    result.sort(
        key=lambda row: (
            -row["points"],
            -row["score_difference"],
            -row["score_for"],
            row["team_name"].casefold(),
            row["team_id"],
        )
    )

    # Assign a unique rank to each team.
    for rank, row in enumerate(result, start=1):
        row["rank"] = rank

    return result