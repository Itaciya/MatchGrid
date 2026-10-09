
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException, NotFoundException
from app.modules.dispute.models.dispute import Dispute
from app.modules.dispute.schemas.dispute import DisputeCreate
from app.modules.match.models.match import Match
from app.modules.player_team.models.player import Player, PlayerStatus


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
