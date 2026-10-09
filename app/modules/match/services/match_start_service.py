from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException
from app.modules.match.models.match import Match
from app.modules.match.services.match_status_service import (
    MATCH_STATUS_LIVE,
    MATCH_STATUS_SCHEDULED,
    transition_match_status,
    validate_status_transition,
)


def start_match(db: Session, match_id: int) -> Match:
    """Start a scheduled match and record the server-side start time."""

    match = (
        db.query(Match)
        .filter(Match.id == match_id)
        .with_for_update()
        .first()
    )

    if match is None:
        from app.core.exceptions import NotFoundException

        raise NotFoundException(detail="Match not found")

    validate_status_transition(match.status, MATCH_STATUS_LIVE)

    if match.team_a_id is None or match.team_b_id is None:
        raise BadRequestException(
            detail="Both teams must be assigned before a match can start"
        )

    match.status = MATCH_STATUS_LIVE
    match.started_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(match)
    except Exception:
        db.rollback()
        raise

    return match
