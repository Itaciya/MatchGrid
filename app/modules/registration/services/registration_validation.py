from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    NotFoundException,
)
from app.modules.player_team.models.player import Player, PlayerStatus
from app.modules.registration.models.registration import Registration
from app.modules.registration.schemas.registration import RegistrationType
from app.modules.tournament.models.tournament import Tournament


def validate_tournament_for_registration(
    db: Session,
    tournament_id: int,
) -> Tournament:
    """Validate whether a tournament is currently accepting registrations."""

    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == tournament_id)
        .first()
    )

    if tournament is None:
        raise NotFoundException(
            detail="Tournament not found"
        )

    now = datetime.now(timezone.utc)

    if tournament.start_date <= now:
        raise BadRequestException(
            detail="Registration deadline has passed"
        )

    if tournament.status != "upcoming":
        raise BadRequestException(
            detail="Registration is not available for this tournament"
        )

    return tournament


def validate_player_eligibility(
    db: Session,
    player_id: int,
) -> Player:
    """Validate whether a player is eligible for individual registration."""

    player = (
        db.query(Player)
        .filter(Player.id == player_id)
        .first()
    )

    if player is None:
        raise NotFoundException(
            detail="Player not found"
        )

    if player.status != PlayerStatus.ACTIVE:
        raise ConflictException(
            detail="Only active players can register for a tournament"
        )

    return player


def validate_duplicate_registration(
    db: Session,
    tournament_id: int,
    player_id: int,
) -> None:
    """Prevent a player from registering for the same tournament twice."""

    existing_registration = (
        db.query(Registration)
        .filter(
            Registration.tournament_id == tournament_id,
            Registration.player_id == player_id,
        )
        .first()
    )

    if existing_registration is not None:
        raise ConflictException(
            detail="Player is already registered for this tournament"
        )


def validate_player_registration(
    db: Session,
    tournament_id: int,
    player_id: int,
) -> Player:
    """Run all validation checks for an individual player registration."""

    validate_tournament_for_registration(
        db,
        tournament_id,
    )

    player = validate_player_eligibility(
        db,
        player_id,
    )

    validate_duplicate_registration(
        db,
        tournament_id,
        player_id,
    )

    return player
