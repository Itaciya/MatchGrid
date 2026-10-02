from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.registration.models.registration import Registration
from app.modules.registration.schemas.registration import (
    RegistrationCreate,
    RegistrationStatus,
    RegistrationType,
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
