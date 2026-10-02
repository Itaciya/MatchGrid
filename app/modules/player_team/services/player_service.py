from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.modules.player_team.models.player import Player, PlayerStatus
from app.modules.player_team.models.team import Team
from app.modules.player_team.schemas.player import (
    PlayerCreate,
    PlayerStatusUpdate,
    PlayerUpdate,
)


def create_player(
    db: Session,
    user_id: int,
    data: PlayerCreate,
) -> Player:
    """Create a player profile for the authenticated user."""

    existing_player = (
        db.query(Player)
        .filter(Player.user_id == user_id)
        .first()
    )

    if existing_player is not None:
        raise ConflictException(
            detail="Player profile already exists for this user"
        )

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


def update_player_profile(
    db: Session,
    player_id: int,
    data: PlayerUpdate,
) -> Player:
    """Update a player's profile information."""

    player = (
        db.query(Player)
        .filter(Player.id == player_id)
        .first()
    )

    if player is None:
        raise NotFoundException(detail="Player not found")

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(player, field, value)

    db.commit()
    db.refresh(player)

    return player


def update_player_status(
    db: Session,
    player_id: int,
    data: PlayerStatusUpdate,
) -> Player:
    """Update a player's eligibility status."""

    player = (
        db.query(Player)
        .filter(Player.id == player_id)
        .first()
    )

    if player is None:
        raise NotFoundException(detail="Player not found")

    player.status = data.status

    db.commit()
    db.refresh(player)

    return player


def add_player_to_team(
    db: Session,
    team_id: int,
    player_id: int,
    captain_id: int,
) -> Player:
    """Add an eligible player to a team."""

    team = (
        db.query(Team)
        .filter(Team.id == team_id)
        .first()
    )

    if team is None:
        raise NotFoundException(detail="Team not found")

    if team.captain_id != captain_id:
        raise ForbiddenException(
            detail="Only the team captain can add players"
        )

    player = (
        db.query(Player)
        .filter(Player.id == player_id)
        .first()
    )

    if player is None:
        raise NotFoundException(detail="Player not found")

    if player.status != PlayerStatus.ACTIVE:
        raise ConflictException(
            detail="Only active players can be added to a team"
        )

    if player.team_id is not None:
        raise ConflictException(
            detail="Player already belongs to a team"
        )

    player.team_id = team_id

    db.commit()
    db.refresh(player)

    return player

def remove_player_from_team(
    db: Session,
    team_id: int,
    player_id: int,
    captain_id: int,
) -> Player:
    """Remove a player from a team."""

    team = (
        db.query(Team)
        .filter(Team.id == team_id)
        .first()
    )

    if team is None:
        raise NotFoundException(detail="Team not found")

    if team.captain_id != captain_id:
        raise ForbiddenException(
            detail="Only the team captain can remove players"
        )

    player = (
        db.query(Player)
        .filter(Player.id == player_id)
        .first()
    )

    if player is None:
        raise NotFoundException(detail="Player not found")

    if player.team_id != team_id:
        raise ConflictException(
            detail="Player does not belong to this team"
        )

    player.team_id = None

    db.commit()
    db.refresh(player)

    return player
