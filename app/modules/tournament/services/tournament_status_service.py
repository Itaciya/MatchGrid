from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException
from app.modules.match.models.match import Match
from app.modules.match.models.match_result import MatchResult
from app.modules.tournament.models.tournament import Tournament

STATUS_UPCOMING = "upcoming"
STATUS_LIVE = "live"
STATUS_COMPLETED = "completed"


def _invalidate_cache() -> None:
    from app.modules.tournament.services.tournament_service import (
        invalidate_public_tournament_cache,
    )

    invalidate_public_tournament_cache()


def mark_tournament_live(db: Session, tournament_id: int) -> bool:
    """upcoming -> live. Does not commit; the caller commits."""
    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == tournament_id)
        .with_for_update()
        .first()
    )
    if tournament is not None and tournament.status == STATUS_UPCOMING:
        tournament.status = STATUS_LIVE
        return True
    return False


def complete_tournament_if_done(db: Session, tournament_id: int) -> bool:
    """live -> completed once every non-cancelled match has a final result."""
    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == tournament_id)
        .with_for_update()
        .first()
    )
    if tournament is None or tournament.status != STATUS_LIVE:
        db.rollback()
        return False

    total = (
        db.query(func.count(Match.id))
        .filter(Match.tournament_id == tournament_id, Match.status != "cancelled")
        .scalar()
    )
    unfinished = (
        db.query(func.count(Match.id))
        .select_from(Match)
        .outerjoin(MatchResult, MatchResult.match_id == Match.id)
        .filter(
            Match.tournament_id == tournament_id,
            Match.status != "cancelled",
            MatchResult.id.is_(None),
        )
        .scalar()
    )
    if not total or unfinished:
        db.rollback()
        return False

    tournament.status = STATUS_COMPLETED
    db.commit()
    _invalidate_cache()
    return True


def end_tournament(db: Session, tournament: Tournament) -> Tournament:
    """Organiser manually ends a live tournament."""
    if tournament.status != STATUS_LIVE:
        raise ConflictException(
            detail=(
                "Only a live tournament can be ended "
                f"(current status: '{tournament.status}')"
            )
        )
    tournament.status = STATUS_COMPLETED
    db.commit()
    db.refresh(tournament)
    _invalidate_cache()
    return tournament
