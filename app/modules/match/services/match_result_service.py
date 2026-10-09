from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.modules.match.models.match import Match
from app.modules.match.models.match_result import (
    OUTCOME_DRAW,
    OUTCOME_TEAM_A_WIN,
    OUTCOME_TEAM_B_WIN,
    MatchResult,
)
from app.modules.score.models.score import Score, ScoreVerificationStatus

MATCH_STATUS_LIVE = "live"
MATCH_STATUS_COMPLETED = "completed"

VERIFIED = ScoreVerificationStatus.VERIFIED.value


def determine_outcome(team_a_score: int, team_b_score: int) -> str:
    """Pure result calculation: who won, or was it a draw."""
    if team_a_score > team_b_score:
        return OUTCOME_TEAM_A_WIN
    if team_b_score > team_a_score:
        return OUTCOME_TEAM_B_WIN
    return OUTCOME_DRAW


def finalize_match_result(
    db: Session,
    match_id: int,
    finalizer_id: int,
) -> MatchResult:
    """Turn a verified score into the match's official result.

    Authorisation (organiser of the match's tournament) is enforced by the
    route dependency verify_match_organiser, not here. The match and score
    rows are locked in the same order score_service and
    score_verification_service use, so finalization cannot interleave with
    a review or a correction.
    """
    match = (
        db.query(Match)
        .filter(Match.id == match_id)
        .with_for_update()
        .first()
    )
    if match is None:
        raise NotFoundException(detail="Match not found")

    existing = (
        db.query(MatchResult)
        .filter(MatchResult.match_id == match_id)
        .first()
    )
    if existing is not None:
        raise ConflictException(
            detail="The result for this match has already been finalized"
        )

    if match.status != MATCH_STATUS_LIVE:
        raise ConflictException(
            detail=(
                "Only a live match can be finalized "
                f"(current status: '{match.status}')"
            )
        )

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

    if score.verification_status != VERIFIED:
        raise ConflictException(
            detail=(
                "Only a verified score can be finalized "
                f"(current score status: '{score.verification_status}')"
            )
        )

    if match.team_a_id is None or match.team_b_id is None:
        raise BadRequestException(
            detail="Both teams must be assigned before a result can be finalized"
        )

    outcome = determine_outcome(score.team_a_score, score.team_b_score)

    if outcome == OUTCOME_TEAM_A_WIN:
        winner_team_id, loser_team_id = match.team_a_id, match.team_b_id
    elif outcome == OUTCOME_TEAM_B_WIN:
        winner_team_id, loser_team_id = match.team_b_id, match.team_a_id
    else:
        winner_team_id, loser_team_id = None, None

    result = MatchResult(
        match_id=match_id,
        outcome=outcome,
        winner_team_id=winner_team_id,
        loser_team_id=loser_team_id,
        team_a_score=score.team_a_score,
        team_b_score=score.team_b_score,
        finalized_by_id=finalizer_id,
        finalized_at=datetime.now(timezone.utc),
    )
    db.add(result)
    match.status = MATCH_STATUS_COMPLETED

    db.commit()
    db.refresh(result)

    return result
