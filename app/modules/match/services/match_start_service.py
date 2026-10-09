from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.modules.match.models.match import Match

MATCH_STATUS_SCHEDULED = "scheduled"
MATCH_STATUS_LIVE = "live"


def start_match(db: Session, match_id: int) -> Match:
    """Move a scheduled match to live and record the start time.

    The start time always comes from the server clock, never from the
    client. The row is locked while the status is checked and changed,
    so two simultaneous start requests cannot both succeed.
    """
    match = (
        db.query(Match)
        .filter(Match.id == match_id)
        .with_for_update()
        .first()
    )

    if match is None:
        raise NotFoundException(detail="Match not found")

    if match.status != MATCH_STATUS_SCHEDULED:
        raise ConflictException(
            detail=f"Match cannot be started from status '{match.status}'"
        )

    if match.team_a_id is None or match.team_b_id is None:
        raise BadRequestException(
            detail="Both teams must be assigned before a match can start"
        )

    match.status = MATCH_STATUS_LIVE
    match.started_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(match)

    return match
