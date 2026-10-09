from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.modules.match.models.match import Match


MATCH_STATUS_SCHEDULED = "scheduled"
MATCH_STATUS_LIVE = "live"
MATCH_STATUS_COMPLETED = "completed"
MATCH_STATUS_CANCELLED = "cancelled"


ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    MATCH_STATUS_SCHEDULED: {MATCH_STATUS_LIVE},
    MATCH_STATUS_LIVE: {MATCH_STATUS_COMPLETED},
    MATCH_STATUS_COMPLETED: set(),
    MATCH_STATUS_CANCELLED: set(),
}


def validate_status_transition(current: str, target: str) -> None:
    """Reject status transitions that are not explicitly allowed."""

    allowed_targets = ALLOWED_STATUS_TRANSITIONS.get(current, set())

    if target not in allowed_targets:
        raise ConflictException(
            detail=(
                f"Match cannot transition from status "
                f"'{current}' to '{target}'"
            )
        )


def transition_match_status(
    db: Session,
    match_id: int,
    target_status: str,
) -> Match:
    """Validate and persist a match status transition."""

    match = (
        db.query(Match)
        .filter(Match.id == match_id)
        .with_for_update()
        .first()
    )

    if match is None:
        raise NotFoundException(detail="Match not found")

    validate_status_transition(match.status, target_status)

    match.status = target_status

    try:
        db.commit()
        db.refresh(match)
    except Exception:
        db.rollback()
        raise

    return match


def complete_match(db: Session, match_id: int) -> Match:
    """Mark a live match as completed."""

    match = (
        db.query(Match)
        .filter(Match.id == match_id)
        .with_for_update()
        .first()
    )

    if match is None:
        raise NotFoundException(detail="Match not found")

    validate_status_transition(
        match.status,
        MATCH_STATUS_COMPLETED,
    )

    if match.team_a_id is None or match.team_b_id is None:
        raise BadRequestException(
            detail="Both teams must be assigned before completing a match"
        )

    match.status = MATCH_STATUS_COMPLETED

    try:
        db.commit()
        db.refresh(match)
    except Exception:
        db.rollback()
        raise

    return match