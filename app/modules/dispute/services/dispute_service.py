
from sqlalchemy.orm import Session
from app.modules.dispute.models.dispute_status_history import DisputeStatusHistory
from app.modules.dispute.schemas.dispute import DisputeStatusUpdate
from app.core.exceptions import ForbiddenException, NotFoundException
from app.modules.dispute.models.dispute import Dispute
from app.modules.dispute.schemas.dispute import DisputeCreate
from app.modules.match.models.match import Match
from app.modules.player_team.models.player import Player, PlayerStatus
from app.modules.tournament.models.tournament import Tournament
from app.modules.dispute.schemas.dispute import (
    DisputeCreate,
    DisputeStatusUpdate,
    DisputeResolutionRequest,
)

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

    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    return dispute


def get_dispute_by_id(
    db: Session,
    current_user_id: int,
    dispute_id: int,
) -> Dispute:
    """Retrieve a dispute for its owner or an active participant in its match."""

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

    # Only the organiser who owns this tournament may update its disputes.
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
            detail=f"Invalid dispute status transition: "
            f"{previous_status} -> {new_status}"
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

def get_pending_disputes_for_organizer(db: Session, current_user_id: int):
    """Return pending disputes for tournaments owned by the organizer."""
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
    """Resolve or reject a dispute by its tournament's authorised organiser."""

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
            detail="Only the tournament owner can resolve this dispute"
        )

    if dispute.status != "under_review":
        raise ForbiddenException(
            detail="Only disputes under review can be resolved"
        )

    previous_status = dispute.status
    new_status = data.decision

    try:
        dispute.status = new_status
        dispute.resolution = data.resolution

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
