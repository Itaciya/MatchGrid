from sqlalchemy.orm import Session

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
