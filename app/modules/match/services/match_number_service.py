from sqlalchemy import func
from sqlalchemy.orm import Session

from app.modules.match.models.match import Match


def get_next_match_number(
    db: Session,
    tournament_id: int,
) -> int:
    """Return the next available match number for a tournament."""

    max_match_number = (
        db.query(func.max(Match.match_number))
        .filter(Match.tournament_id == tournament_id)
        .scalar()
    )

    if max_match_number is None:
        return 1

    return max_match_number + 1


def generate_match_number(
    db: Session,
    tournament_id: int,
) -> int:
    """Generate a unique match number for a tournament."""

    next_number = get_next_match_number(
        db,
        tournament_id,
    )

    while (
        db.query(Match.id)
        .filter(
            Match.tournament_id == tournament_id,
            Match.match_number == next_number,
        )
        .first()
        is not None
    ):
        next_number += 1

    return next_number