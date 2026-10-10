from sqlalchemy.orm import Session

from app.modules.match.models.match import Match
from app.modules.match.models.match_result import MatchResult

POINTS_FOR_WIN = 3
POINTS_FOR_DRAW = 1
POINTS_FOR_LOSS = 0


def _empty_row(team_id: int) -> dict:
    return {
        "team_id": team_id,
        "played": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_for": 0,
        "goals_against": 0,
        "goal_difference": 0,
        "points": 0,
    }


def _apply(row: dict, scored: int, conceded: int) -> None:
    row["played"] += 1
    row["goals_for"] += scored
    row["goals_against"] += conceded
    row["goal_difference"] = row["goals_for"] - row["goals_against"]

    if scored > conceded:
        row["wins"] += 1
        row["points"] += POINTS_FOR_WIN
    elif scored == conceded:
        row["draws"] += 1
        row["points"] += POINTS_FOR_DRAW
    else:
        row["losses"] += 1
        row["points"] += POINTS_FOR_LOSS


def get_tournament_standings(db: Session, tournament_id: int) -> list[dict]:
    """League table for a tournament, derived from its finalized results.

    Computed on every read from match_results instead of being stored, so a
    corrected result (SCRUM-151) is reflected immediately and the table
    cannot drift out of step. Only finalized results count: a score that has
    not been finalized does not affect the standings. A team appears once it
    is assigned to any of the tournament's matches.
    """
    table: dict[int, dict] = {}

    matches = db.query(Match).filter(Match.tournament_id == tournament_id).all()
    for match in matches:
        for team_id in (match.team_a_id, match.team_b_id):
            if team_id is not None:
                table.setdefault(team_id, _empty_row(team_id))

    finalized = (
        db.query(Match, MatchResult)
        .join(MatchResult, MatchResult.match_id == Match.id)
        .filter(Match.tournament_id == tournament_id)
        .all()
    )
    for match, result in finalized:
        if match.team_a_id is None or match.team_b_id is None:
            continue
        _apply(
            table.setdefault(match.team_a_id, _empty_row(match.team_a_id)),
            result.team_a_score,
            result.team_b_score,
        )
        _apply(
            table.setdefault(match.team_b_id, _empty_row(match.team_b_id)),
            result.team_b_score,
            result.team_a_score,
        )

    return sorted(
        table.values(),
        key=lambda r: (
            -r["points"],
            -r["goal_difference"],
            -r["goals_for"],
            r["team_id"],
        ),
    )
