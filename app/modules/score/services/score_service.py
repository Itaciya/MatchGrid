from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.modules.match.models.match import Match
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


def _ensure_not_finalized(match: Match, score: Score | None) -> None:
    if match.status == MATCH_STATUS_COMPLETED or (
        score is not None and score.is_verified
    ):
        raise ConflictException(detail="Finalized scores cannot be modified")


def _ensure_match_is_live(match: Match) -> None:
    if match.status != MATCH_STATUS_LIVE:
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
        _ensure_not_finalized(match, existing)
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

    _ensure_not_finalized(match, score)
    _ensure_match_is_live(match)

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
