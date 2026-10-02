from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.modules.player_team.models.player import Player
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.player_team.services.player_service import (
    validate_team_roster,
)
from app.modules.registration.models.registration import Registration
from app.modules.registration.schemas.registration import (
    RegistrationCreate,
    RegistrationStatus,
    RegistrationType,
    RegistrationUpdate,
)
from app.modules.registration.services.registration_validation import (
    validate_player_registration,
)
from app.modules.tournament.models.tournament import Tournament


def create_team_registration(
    db: Session,
    current_user_id: int,
    data: RegistrationCreate,
) -> Registration:
    """Create a tournament registration for the authenticated team captain."""

    # This endpoint is only for team registration.
    if data.registration_type != RegistrationType.TEAM:
        raise BadRequestException(
            detail="Only team registration is allowed"
        )

    if data.team_id is None:
        raise BadRequestException(
            detail="team_id is required for team registration"
        )

    # Check that the team exists.
    team = (
        db.query(Team)
        .filter(Team.id == data.team_id)
        .first()
    )

    if team is None:
        raise NotFoundException(detail="Team not found")

    # Only the team captain can register the team.
    if team.captain_id != current_user_id:
        raise ForbiddenException(
            detail="Only the team captain can register the team"
        )

    # Team must be active.
    if team.status != TeamStatus.ACTIVE:
        raise BadRequestException(
            detail="Only active teams can register"
        )

    # Validate the team's complete roster before registration.
    player_ids = [player.id for player in team.players]

    validate_team_roster(
        db,
        player_ids,
        team_id=team.id,
    )

    # Check that the tournament exists.
    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == data.tournament_id)
        .first()
    )

    if tournament is None:
        raise NotFoundException(detail="Tournament not found")

    # Registration is allowed before the tournament starts.
    now = datetime.now(timezone.utc)

    if tournament.start_date <= now:
        raise BadRequestException(
            detail="Registration is not available for this tournament"
        )

    # If the tournament has already been marked with a non-upcoming
    # status, do not allow a new registration.
    if tournament.status != "upcoming":
        raise BadRequestException(
            detail="Registration is not available for this tournament"
        )

    # Prevent duplicate registration.
    existing_registration = (
        db.query(Registration)
        .filter(
            Registration.tournament_id == data.tournament_id,
            Registration.team_id == data.team_id,
        )
        .first()
    )

    if existing_registration is not None:
        raise ConflictException(
            detail="Team is already registered for this tournament"
        )

    registration = Registration(
        tournament_id=data.tournament_id,
        team_id=data.team_id,
        player_id=None,
        registration_type=RegistrationType.TEAM.value,
        status=RegistrationStatus.PENDING.value,
        note=data.note,
    )

    db.add(registration)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictException(
            detail="Team is already registered for this tournament"
        )

    db.refresh(registration)

    return registration


def create_player_registration(
    db: Session,
    current_user_id: int,
    data: RegistrationCreate,
) -> Registration:
    """Create a tournament registration for the authenticated player."""

    # This function is only for individual player registration.
    if data.registration_type != RegistrationType.PLAYER:
        raise BadRequestException(
            detail="Only player registration is allowed"
        )

    if data.player_id is None:
        raise BadRequestException(
            detail="player_id is required for player registration"
        )

    # Find the player profile belonging to the authenticated user.
    player = (
        db.query(Player)
        .filter(Player.user_id == current_user_id)
        .first()
    )

    if player is None:
        raise NotFoundException(
            detail="Player profile not found"
        )

    # A player can only register their own profile.
    if data.player_id != player.id:
        raise ForbiddenException(
            detail="You can only register your own player profile"
        )

    # Validate tournament, player eligibility, and duplicate registration.
    validate_player_registration(
        db,
        data.tournament_id,
        player.id,
    )

    # Create the player registration with pending status.
    registration = Registration(
        tournament_id=data.tournament_id,
        team_id=None,
        player_id=player.id,
        registration_type=RegistrationType.PLAYER.value,
        status=RegistrationStatus.PENDING.value,
        note=data.note,
    )

    db.add(registration)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictException(
            detail="Player is already registered for this tournament"
        )

    db.refresh(registration)

    return registration


def update_registration_status(
    db: Session,
    registration_id: int,
    new_status: RegistrationStatus,
) -> Registration:
    """Update registration status using valid status transitions."""

    registration = (
        db.query(Registration)
        .filter(Registration.id == registration_id)
        .first()
    )

    if registration is None:
        raise NotFoundException(detail="Registration not found")

    current_status = RegistrationStatus(registration.status)

    valid_transitions = {
        RegistrationStatus.PENDING: {
            RegistrationStatus.APPROVED,
            RegistrationStatus.REJECTED,
        },
        RegistrationStatus.APPROVED: set(),
        RegistrationStatus.REJECTED: set(),
    }

    if new_status not in valid_transitions[current_status]:
        raise BadRequestException(
            detail=(
                f"Invalid status transition: "
                f"{current_status.value} to {new_status.value}"
            )
        )

    registration.status = new_status.value
    registration.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(registration)

    return registration


def get_pending_registrations(
    db: Session,
    tournament_id: int,
) -> list[Registration]:
    """Retrieve all pending registrations for a tournament."""

    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == tournament_id)
        .first()
    )

    if tournament is None:
        raise NotFoundException(detail="Tournament not found")

    registrations = (
        db.query(Registration)
        .filter(
            Registration.tournament_id == tournament_id,
            Registration.status == RegistrationStatus.PENDING.value,
        )
        .all()
    )

    return registrations


def approve_registration(
    db: Session,
    registration_id: int,
) -> Registration:
    """Approve a valid pending registration."""

    registration = (
        db.query(Registration)
        .filter(Registration.id == registration_id)
        .first()
    )

    if registration is None:
        raise NotFoundException(detail="Registration not found")

    # Only pending registrations can be approved.
    if registration.status != RegistrationStatus.PENDING.value:
        raise BadRequestException(
            detail="Only pending registrations can be approved"
        )

    # Validate player registration.
    if registration.registration_type == RegistrationType.PLAYER:
        if registration.player_id is None:
            raise BadRequestException(
                detail="Invalid player registration"
            )

        player = (
            db.query(Player)
            .filter(Player.id == registration.player_id)
            .first()
        )

        if player is None:
            raise NotFoundException(detail="Player not found")

        if player.status != "active":
            raise BadRequestException(
                detail="Only active players can be approved"
            )

    # Validate team registration.
    elif registration.registration_type == RegistrationType.TEAM:
        if registration.team_id is None:
            raise BadRequestException(
                detail="Invalid team registration"
            )

        team = (
            db.query(Team)
            .filter(Team.id == registration.team_id)
            .first()
        )

        if team is None:
            raise NotFoundException(detail="Team not found")

        if team.status != TeamStatus.ACTIVE:
            raise BadRequestException(
                detail="Only active teams can be approved"
            )

        player_ids = [player.id for player in team.players]

        validate_team_roster(
            db,
            player_ids,
            team_id=team.id,
        )

    registration.status = RegistrationStatus.APPROVED.value
    registration.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(registration)

    return registration


def update_registration(
    db: Session,
    registration_id: int,
    current_user_id: int,
    data: RegistrationUpdate,
) -> Registration:
    """Update an editable registration by an authorized participant."""

    registration = (
        db.query(Registration)
        .filter(Registration.id == registration_id)
        .first()
    )

    if registration is None:
        raise NotFoundException(detail="Registration not found")

    # Only pending registrations can be edited.
    if registration.status != RegistrationStatus.PENDING.value:
        raise BadRequestException(
            detail="Only pending registrations can be updated"
        )

    # Verify participant ownership.
    if registration.registration_type == RegistrationType.PLAYER:
        if registration.player_id is None:
            raise BadRequestException(
                detail="Invalid player registration"
            )

        player = (
            db.query(Player)
            .filter(Player.id == registration.player_id)
            .first()
        )

        if player is None:
            raise NotFoundException(detail="Player not found")

        if player.user_id != current_user_id:
            raise ForbiddenException(
                detail="You can only update your own registration"
            )

    elif registration.registration_type == RegistrationType.TEAM:
        if registration.team_id is None:
            raise BadRequestException(
                detail="Invalid team registration"
            )

        team = (
            db.query(Team)
            .filter(Team.id == registration.team_id)
            .first()
        )

        if team is None:
            raise NotFoundException(detail="Team not found")

        if team.captain_id != current_user_id:
            raise ForbiddenException(
                detail="Only the team captain can update this registration"
            )

    else:
        raise BadRequestException(
            detail="Invalid registration type"
        )

    # Update only editable information.
    if data.note is not None:
        registration.note = data.note

    db.commit()
    db.refresh(registration)

    return registration


def reject_registration(
    db: Session,
    registration_id: int,
) -> Registration:
    """Reject a pending registration."""

    registration = (
        db.query(Registration)
        .filter(Registration.id == registration_id)
        .first()
    )

    if registration is None:
        raise NotFoundException(detail="Registration not found")

    # Only pending registrations can be rejected.
    if registration.status != RegistrationStatus.PENDING.value:
        raise BadRequestException(
            detail="Only pending registrations can be rejected"
        )

    registration.status = RegistrationStatus.REJECTED.value
    registration.reviewed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(registration)

    return registration
