
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.modules.dispute.models.dispute import Dispute
from app.modules.dispute.models.dispute_status_history import (
    DisputeStatusHistory,
)
from app.modules.dispute.schemas.dispute import (
    DisputeCreate,
    DisputeResolutionRequest,
    DisputeStatusUpdate,
)
from app.modules.match.models.match import Match
from app.modules.player_team.models.player import Player, PlayerStatus
from app.modules.score.models.score import Score, ScoreVerificationStatus
from app.modules.tournament.models.tournament import Tournament


def create_dispute(
    db: Session,
    current_user_id: int,
    data: DisputeCreate,
) -> Dispute:
    """Create a pending dispute for an authenticated match participant."""

    match = (
        db.query(Match)
        .filter(Match.id == data.match_id)
        .first()
    )

    if match is None:
        raise NotFoundException(detail="Match not found")

    player = (
        db.query(Player)
        .filter(Player.user_id == current_user_id)
        .first()
    )

    if player is None:
        raise ForbiddenException(
            detail="Only a match participant can submit a dispute"
        )

    if player.status != PlayerStatus.ACTIVE:
        raise ForbiddenException(
            detail="Only active players can submit a dispute"
        )

    if player.team_id not in (match.team_a_id, match.team_b_id):
        raise ForbiddenException(
            detail="You are not a participant in this match"
        )

    dispute = Dispute(
        match_id=match.id,
        user_id=current_user_id,
        reason=data.reason,
        status="pending",
    )

    try:
        db.add(dispute)
        db.commit()
        db.refresh(dispute)
    except Exception:
        db.rollback()
        raise

    return dispute


def get_dispute_by_id(
    db: Session,
    current_user_id: int,
    dispute_id: int,
) -> Dispute:
    """Retrieve a dispute for its owner or an active participant."""

    dispute = (
        db.query(Dispute)
        .filter(Dispute.id == dispute_id)
        .first()
    )

    if dispute is None:
        raise NotFoundException(detail="Dispute not found")

    # The dispute creator can view their own dispute.
    if dispute.user_id == current_user_id:
        return dispute

    match = (
        db.query(Match)
        .filter(Match.id == dispute.match_id)
        .first()
    )

    if match is None:
        raise NotFoundException(detail="Match not found")

    player = (
        db.query(Player)
        .filter(Player.user_id == current_user_id)
        .first()
    )

    if (
        player is None
        or player.status != PlayerStatus.ACTIVE
        or player.team_id not in (match.team_a_id, match.team_b_id)
    ):
        raise ForbiddenException(
            detail="You do not have permission to view this dispute"
        )

    return dispute


def get_disputes_by_match(
    db: Session,
    current_user_id: int,
    match_id: int,
) -> list[Dispute]:
    """Retrieve disputes for a match only for its active participants."""

    match = (
        db.query(Match)
        .filter(Match.id == match_id)
        .first()
    )

    if match is None:
        raise NotFoundException(detail="Match not found")

    player = (
        db.query(Player)
        .filter(Player.user_id == current_user_id)
        .first()
    )

    if (
        player is None
        or player.status != PlayerStatus.ACTIVE
        or player.team_id not in (match.team_a_id, match.team_b_id)
    ):
        raise ForbiddenException(
            detail="You do not have permission to view disputes for this match"
        )

    return (
        db.query(Dispute)
        .filter(Dispute.match_id == match_id)
        .order_by(Dispute.created_at.desc())
        .all()
    )


def update_dispute_status(
    db: Session,
    current_user_id: int,
    dispute_id: int,
    data: DisputeStatusUpdate,
) -> Dispute:
    """Update a dispute status if the organiser owns its tournament."""

    dispute = (
        db.query(Dispute)
        .filter(Dispute.id == dispute_id)
        .first()
    )

    if dispute is None:
        raise NotFoundException(detail="Dispute not found")

    match = (
        db.query(Match)
        .filter(Match.id == dispute.match_id)
        .first()
    )

    if match is None:
        raise NotFoundException(detail="Match not found")

    if match.tournament.organizer_id != current_user_id:
        raise ForbiddenException(
            detail="Only the tournament owner can update dispute status"
        )

    allowed_transitions = {
        "pending": {"under_review"},
        "under_review": {"resolved", "rejected"},
        "resolved": set(),
        "rejected": set(),
    }

    previous_status = dispute.status
    new_status = data.status

    if new_status not in allowed_transitions.get(previous_status, set()):
        raise ForbiddenException(
            detail=(
                "Invalid dispute status transition: "
                f"{previous_status} -> {new_status}"
            )
        )

    try:
        dispute.status = new_status

        history = DisputeStatusHistory(
            dispute_id=dispute.id,
            previous_status=previous_status,
            new_status=new_status,
            changed_by=current_user_id,
        )
        db.add(history)

        db.commit()
        db.refresh(dispute)

    except Exception:
        db.rollback()
        raise

    return dispute


def get_pending_disputes_for_organizer(
    db: Session,
    current_user_id: int,
) -> list[Dispute]:
    """Return pending disputes for tournaments owned by the organiser."""

    return (
        db.query(Dispute)
        .join(Match, Dispute.match_id == Match.id)
        .join(Tournament, Match.tournament_id == Tournament.id)
        .filter(
            Tournament.organizer_id == current_user_id,
            Dispute.status == "pending",
        )
        .order_by(Dispute.created_at.desc())
        .all()
    )


def resolve_dispute(
    db: Session,
    current_user_id: int,
    dispute_id: int,
    data: DisputeResolutionRequest,
) -> Dispute:
    """
    Resolve or reject a dispute by the authorised tournament organiser.

    When a score exists, the final dispute decision can apply approved
    score corrections, verify the result, and complete a live match.
    The score, match, dispute, and history changes share one transaction.
    """

    # Read the dispute first to identify its match.
    initial_dispute = (
        db.query(Dispute)
        .filter(Dispute.id == dispute_id)
        .first()
    )

    if initial_dispute is None:
        raise NotFoundException(detail="Dispute not found")

    # Lock the match first, following the match -> score lock order.
    match = (
        db.query(Match)
        .filter(Match.id == initial_dispute.match_id)
        .with_for_update()
        .first()
    )

    if match is None:
        raise NotFoundException(detail="Match not found")

    try:
        # Only the organiser who owns this tournament may resolve the dispute.
        if match.tournament.organizer_id != current_user_id:
            raise ForbiddenException(
                detail="Only the tournament owner can resolve this dispute"
            )

        corrected_a = data.corrected_team_a_score
        corrected_b = data.corrected_team_b_score
        new_status = data.decision

        if new_status not in {"resolved", "rejected"}:
            raise BadRequestException(
                detail="The dispute decision must be resolved or rejected"
            )

        # A correction must include both teams' scores.
        if (corrected_a is None) != (corrected_b is None):
            raise BadRequestException(
                detail=(
                    "Both corrected team scores must be provided together"
                )
            )

        # A rejected dispute cannot apply proposed score corrections.
        if new_status == "rejected" and (
            corrected_a is not None or corrected_b is not None
        ):
            raise BadRequestException(
                detail=(
                    "Score corrections can only be applied to a resolved dispute"
                )
            )

        # Lock the score after locking the match.
        score = (
            db.query(Score)
            .filter(Score.match_id == match.id)
            .with_for_update()
            .first()
        )

        # Re-fetch and lock the dispute, so its latest status is checked.
        dispute = (
            db.query(Dispute)
            .filter(Dispute.id == dispute_id)
            .populate_existing()
            .with_for_update()
            .first()
        )

        if dispute is None:
            raise NotFoundException(detail="Dispute not found")

        if dispute.match_id != match.id:
            raise ConflictException(
                detail="The dispute's match changed while it was being resolved"
            )

        if dispute.status != "under_review":
         raise ForbiddenException(
        detail=(
            "Only disputes under review can be resolved "
            f"(current status: '{dispute.status}')"
        )
    )

        # Score correction requires an existing submitted score.
        if score is None and (
            corrected_a is not None or corrected_b is not None
        ):
            raise ConflictException(
                detail=(
                    "Cannot apply score corrections because no score "
                    "has been submitted for this match"
                )
            )

        previous_status = dispute.status

        if score is not None:
            if match.status not in {"live", "completed"}:
                raise ConflictException(
                    detail=(
                        "A result can only be finalized for a live or "
                        "completed match "
                        f"(current status: '{match.status}')"
                    )
                )

            # Apply score changes only when the organiser approves them.
            if new_status == "resolved" and corrected_a is not None:
                score.team_a_score = corrected_a
                score.team_b_score = corrected_b

            # Whether the dispute is resolved or rejected, the score that
            # remains after the decision becomes the official result.
            now = datetime.now(timezone.utc)

            score.verification_status = (
                ScoreVerificationStatus.VERIFIED.value
            )
            score.is_verified = True
            score.reviewed_by_id = current_user_id
            score.reviewed_at = now

            # A live match becomes completed. An already-completed match
            # stays completed so a corrected result can replace its score.
            if match.status == "live":
                match.status = "completed"

        # Close the dispute only after all validations have passed.
        dispute.status = new_status
        dispute.resolution = data.resolution

        history = DisputeStatusHistory(
            dispute_id=dispute.id,
            previous_status=previous_status,
            new_status=new_status,
            changed_by=current_user_id,
        )
        db.add(history)

        # Persist the result, match status, dispute, and history atomically.
        db.commit()
        db.refresh(dispute)

        return dispute

    except Exception:
        db.rollback()
        raise
