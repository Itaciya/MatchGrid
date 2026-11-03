from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.match.models.match import Match
from app.modules.match.models.match_result import MatchResult
from app.modules.score.models.score import Score, ScoreVerificationStatus
from app.modules.score.schemas.score import ScoreCreate, ScoreUpdate

MATCH_STATUS_LIVE = "live"
MATCH_STATUS_COMPLETED = "completed"


def _lock_match(db: Session, match_id: int) -> Match:
    """Fetch the match with a row lock so concurrent writes are serialised."""
    match = (
        db.query(Match)
        .filter(Match.id == match_id)
        .with_for_update()
        .first()
    )

    if match is None:
        raise NotFoundException(detail="Match not found")

    return match


def _ensure_not_finalized(
    db: Session, match: Match, score: Score | None
) -> None:
    """Reject edits once the score is verified or the result is finalized.

    A match the scorer has ended is only "completed", not finalized: the
    organiser may still reject the score, and then the scorer can fix it.
    """
    finalized = (
        db.query(MatchResult.id)
        .filter(MatchResult.match_id == match.id)
        .first()
        is not None
    )
    if finalized or (score is not None and score.is_verified):
        raise ConflictException(detail="Finalized scores cannot be modified")

    if match.status == MATCH_STATUS_COMPLETED and (
        score is None
        or score.verification_status
        != ScoreVerificationStatus.REJECTED.value
    ):
        raise ConflictException(
            detail=(
                "The match has ended, so the score can no longer be changed "
                "unless the organiser rejects it for correction"
            )
        )


def _ensure_match_is_live(match: Match, allow_ended: bool = False) -> None:
    # allow_ended lets update_score reach a rejected score on an ended match;
    # _ensure_not_finalized has already restricted that case.
    allowed = (MATCH_STATUS_LIVE, MATCH_STATUS_COMPLETED) if allow_ended else (MATCH_STATUS_LIVE,)
    if match.status not in allowed:
        raise ConflictException(
            detail=(
                "Scores can only be changed while a match is live "
                f"(current status: '{match.status}')"
            )
        )


def create_score(db: Session, match_id: int, data: ScoreCreate) -> Score:
    """Submit the first score for a live match.

    Authorisation (role + match assignment) is enforced by the route
    dependency verify_assigned_official, not here.
    """
    match = _lock_match(db, match_id)

    existing = db.query(Score).filter(Score.match_id == match_id).first()
    if existing is not None:
        _ensure_not_finalized(db, match, existing)
        raise ConflictException(
            detail="A score already exists for this match; update it instead"
        )

    _ensure_match_is_live(match)

    score = Score(
        match_id=match_id,
        team_a_score=data.team_a_score,
        team_b_score=data.team_b_score,
    )
    db.add(score)
    db.commit()
    db.refresh(score)

    return score


def update_score(db: Session, match_id: int, data: ScoreUpdate) -> Score:
    """Update the score of a live, non-finalized match."""
    match = _lock_match(db, match_id)

    score = (
        db.query(Score)
        .filter(Score.match_id == match_id)
        .with_for_update()
        .first()
    )
    if score is None:
        raise NotFoundException(
            detail="No score has been submitted for this match"
        )

    _ensure_not_finalized(db, match, score)
    _ensure_match_is_live(match, allow_ended=True)

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(score, field, value)

    # A rejected score that has been corrected must be reviewed again.
    if score.verification_status == ScoreVerificationStatus.REJECTED.value:
        score.verification_status = ScoreVerificationStatus.PENDING.value
        score.reviewed_by_id = None
        score.reviewed_at = None

    db.commit()
    db.refresh(score)

    return score


def get_score(db: Session, match_id: int) -> Score:
    """Return the current score for a match (any match status)."""
    score = db.query(Score).filter(Score.match_id == match_id).first()
    if score is None:
        raise NotFoundException(
            detail="No score has been submitted for this match"
        )
    return score