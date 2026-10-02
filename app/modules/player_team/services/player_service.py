from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.modules.player_team.models.player import Player
from app.modules.player_team.schemas.player import PlayerCreate


def create_player(
    db: Session,
    user_id: int,
    data: PlayerCreate,
) -> Player:
    """Create a player profile for the authenticated user."""

    player = Player(
        user_id=user_id,
        team_id=data.team_id,
        first_name=data.first_name,
        last_name=data.last_name,
    )

    db.add(player)
    db.commit()
    db.refresh(player)

    return player


def get_player(
    db: Session,
    player_id: int,
) -> Player:
    """Retrieve a player profile by player ID."""

    player = (
        db.query(Player)
        .filter(Player.id == player_id)
        .first()
    )

    if player is None:
        raise NotFoundException(detail="Player not found")

    return player