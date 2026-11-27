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
from app.modules.match.models.match_result_correction import MatchResultCorrection
from app.modules.match.services.single_elimination_service import (
    advance_single_elimination_winner,
    is_knockout_format,
    place_team_in_next_match,
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

    if match.status != MATCH_STATUS_COMPLETED:
        raise ConflictException(
            detail=(
                "The scorer must end the match before its result can be "
                f"finalized (current status: '{match.status}')"
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

    if outcome == OUTCOME_DRAW and is_knockout_format(match.tournament.format):
        raise ConflictException(
            detail=(
                "A knockout match cannot end in a draw. Record the tie-break "
                "result in the score before finalizing."
            )
        )

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

    _notify_result_published(db, match, result)

    # Advance the winner in the same transaction, so the result and the
    # bracket update are saved together or not at all.
    try:
        advance_single_elimination_winner(db, match_id, result)
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(result)

    from app.modules.tournament.services.tournament_status_service import (
        complete_tournament_if_done,
    )

    complete_tournament_if_done(db, match.tournament_id)

    return result


def _notify_result_published(db: Session, match: Match, result: MatchResult) -> None:
    """Followers, and both teams in league formats, see the official result.

    In knockout formats the teams already get an advanced/eliminated
    notification from the bracket, so only followers are told here.
    """
    from app.modules.notification.services import notifier

    team_a = match.team_a.name if match.team_a else "Team A"
    team_b = match.team_b.name if match.team_b else "Team B"
    recipients = notifier.follower_ids(db, match.tournament_id)
    if not is_knockout_format(match.tournament.format):
        recipients |= notifier.team_member_ids(db, (match.team_a_id, match.team_b_id))

    notifier.notify(
        db,
        recipients,
        "result_published",
        f"Result published: {team_a} {result.team_a_score} - "
        f"{result.team_b_score} {team_b}.",
        notifier.tournament_link(match.tournament_id),
    )


def correct_match_result(
    db: Session,
    match_id: int,
    corrector_id: int,
    team_a_score: int,
    team_b_score: int,
    reason: str,
) -> MatchResult:
    """Correct the finalized result of a match and record why.

    Authorisation (organiser of the match's tournament) is enforced by the
    route dependency verify_match_organiser, not here. The result, the score
    it came from and the audit row are written in one transaction: all three
    or none. Standings are derived from match_results when read, so they
    reflect the correction with nothing separate to recalculate.
    """
    match = (
        db.query(Match)
        .filter(Match.id == match_id)
        .with_for_update()
        .first()
    )
    if match is None:
        raise NotFoundException(detail="Match not found")

    result = (
        db.query(MatchResult)
        .filter(MatchResult.match_id == match_id)
        .with_for_update()
        .first()
    )
    if result is None:
        raise NotFoundException(
            detail="No finalized result exists for this match"
        )

    if (team_a_score, team_b_score) == (
        result.team_a_score,
        result.team_b_score,
    ):
        raise BadRequestException(
            detail="The corrected scores are the same as the current result"
        )

    if match.team_a_id is None or match.team_b_id is None:
        raise BadRequestException(
            detail="Both teams must be assigned before a result can be corrected"
        )

    new_outcome = determine_outcome(team_a_score, team_b_score)
    knockout = is_knockout_format(match.tournament.format)

    if new_outcome == OUTCOME_DRAW and knockout:
        raise ConflictException(
            detail="A knockout match result cannot be corrected to a draw"
        )

    if new_outcome == OUTCOME_TEAM_A_WIN:
        winner_team_id, loser_team_id = match.team_a_id, match.team_b_id
    elif new_outcome == OUTCOME_TEAM_B_WIN:
        winner_team_id, loser_team_id = match.team_b_id, match.team_a_id
    else:
        winner_team_id, loser_team_id = None, None

    # In a knockout bracket a changed winner must replace the old winner in
    # the next round, as long as that next match has not started.
    if (
        knockout
        and match.tournament.format == "single_elimination"
        and winner_team_id != result.winner_team_id
    ):
        place_team_in_next_match(
            db,
            match,
            winner_team_id,
            replace_team_id=result.winner_team_id,
        )

    db.add(
        MatchResultCorrection(
            match_result_id=result.id,
            corrected_by_id=corrector_id,
            old_team_a_score=result.team_a_score,
            old_team_b_score=result.team_b_score,
            new_team_a_score=team_a_score,
            new_team_b_score=team_b_score,
            old_outcome=result.outcome,
            new_outcome=new_outcome,
            reason=reason,
        )
    )

    result.team_a_score = team_a_score
    result.team_b_score = team_b_score
    result.outcome = new_outcome
    result.winner_team_id = winner_team_id
    result.loser_team_id = loser_team_id

    # Keep the score the result was built from in step with it.
    score = (
        db.query(Score)
        .filter(Score.match_id == match_id)
        .with_for_update()
        .first()
    )
    if score is not None:
        score.team_a_score = team_a_score
        score.team_b_score = team_b_score
        score.reviewed_by_id = corrector_id
        score.reviewed_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(result)

    return result
