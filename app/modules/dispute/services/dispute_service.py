
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

    # Check whether the match exists.
    match = (
        db.query(Match)
        .filter(Match.id == data.match_id)
        .first()
    )

    if match is None:
        raise NotFoundException(detail="Match not found")

    # Find the authenticated user's player profile.
    player = (
        db.query(Player)
        .filter(Player.user_id == current_user_id)
        .first()
    )

    # Only users with a player profile can submit disputes.
    if player is None:
        raise ForbiddenException(
            detail="Only a match participant can submit a dispute"
        )

    # Only active players can submit disputes.
    if player.status != PlayerStatus.ACTIVE:
        raise ForbiddenException(
            detail="Only active players can submit a dispute"
        )

    # Verify that the player's team participates in this match.
    if player.team_id not in (match.team_a_id, match.team_b_id):
        raise ForbiddenException(
            detail="You are not a participant in this match"
        )

    # Create the dispute with pending status.
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
