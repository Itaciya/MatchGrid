from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.modules.match.models.match import Match
from app.modules.score.models.score import Score, ScoreVerificationStatus

MATCH_STATUS_LIVE = "live"

PENDING = ScoreVerificationStatus.PENDING.value
VERIFIED = ScoreVerificationStatus.VERIFIED.value
REJECTED = ScoreVerificationStatus.REJECTED.value

# Allowed state changes. verified is final. A rejected score only returns to
# pending when its official corrects it (see score_service.update_score);
# it can never go straight to verified.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    PENDING: {VERIFIED, REJECTED},
    REJECTED: {PENDING},
    VERIFIED: set(),
}


def ensure_transition_allowed(current: str, target: str) -> None:
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ConflictException(
            detail=f"A score that is {current} cannot be marked {target}"
        )


def review_score(
    db: Session,
    match_id: int,
    reviewer_id: int,
    decision: str,
) -> Score:
    """Verify or reject a submitted score.

    Authorisation (organiser of the match's tournament) is enforced by the
    route dependency verify_match_organiser, not here. The match and score
    rows are locked, in the same order score_service uses, so reviews and
    corrections cannot interleave.
    """
    match = (
        db.query(Match)
        .filter(Match.id == match_id)
        .with_for_update()
        .first()
    )
    if match is None:
        raise NotFoundException(detail="Match not found")

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

    ensure_transition_allowed(score.verification_status, decision)

    if match.status != MATCH_STATUS_LIVE:
        raise ConflictException(
            detail=(
                "Scores can only be reviewed while a match is live "
                f"(current status: '{match.status}')"
            )
        )

    if match.team_a_id is None or match.team_b_id is None:
        raise BadRequestException(
            detail="Both teams must be assigned before a score can be reviewed"
        )

    score.verification_status = decision
    score.is_verified = decision == VERIFIED
    score.reviewed_by_id = reviewer_id
    score.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(score)

    return score
