from sqlalchemy import and_, or_, select

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)
from app.modules.notification.models.notification import Notification
from app.modules.notification.services.notifier import (
    MY_REGISTRATIONS_LINK,
    approvals_link,
    notify,
)
from app.modules.player_team.models.player import Player
from app.modules.player_team.models.team import Team, TeamStatus
from app.modules.registration.models.registration import Registration
from app.modules.registration.schemas.registration import (
    RegistrationCreate,
    RegistrationStatus,
    RegistrationType,
    RegistrationUpdate,
)
from app.modules.registration.services.registration_validation import (
    validate_player_registration,
    validate_tournament_for_registration,
)
from app.modules.tournament.models.tournament import Tournament
from app.modules.tournament_team.models.tournament_team import TournamentTeam


def notify_registration_status(
    db: Session,
    registration: Registration,
) -> None:
    """Create a notification when registration is approved or rejected."""

    if registration.status not in {
        RegistrationStatus.APPROVED.value,
        RegistrationStatus.REJECTED.value,
    }:
        return

    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == registration.tournament_id)
        .first()
    )

    if tournament is None:
        raise NotFoundException(detail="Tournament not found")

    # Find the user who should receive the notification.
    if registration.registration_type == RegistrationType.PLAYER.value:
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

        recipient_id = player.user_id

    elif registration.registration_type == RegistrationType.TEAM.value:
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

        # The team captain receives the team registration notification.
        recipient_id = team.captain_id

    else:
        raise BadRequestException(detail="Invalid registration type")

    status = registration.status

    if registration.registration_type == RegistrationType.TEAM.value:
        subject = f"{team.name}'s registration"
    else:
        subject = "Your registration"

    if status == RegistrationStatus.APPROVED.value:
        message = (
            f"{subject} for {tournament.name} has been approved. "
            "You will be notified when fixtures are published."
        )
    else:
        message = (
            f"{subject} for {tournament.name} has been rejected by the organiser."
        )

    # Avoid creating the same notification more than once.
    existing_notification = (
        db.query(Notification)
        .filter(
            Notification.user_id == recipient_id,
            Notification.notification_type == "registration_status",
            Notification.content == message,
        )
        .first()
    )

    if existing_notification is not None:
        return

    # Add the notification to the current transaction.
    # Do not commit here; the calling status function commits both changes.
    notification = Notification(
        user_id=recipient_id,
        notification_type="registration_status",
        content=message,
        link=MY_REGISTRATIONS_LINK,
        is_read=False,
    )

    db.add(notification)


def _notify_organiser_of_application(
    db: Session,
    registration: Registration,
    applicant: str,
) -> None:
    """Tell the tournament's organiser that an application needs review."""
    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == registration.tournament_id)
        .first()
    )
    if tournament is None:
        return

    notify(
        db,
        [tournament.organizer_id],
        "registration_submitted",
        f"{applicant} applied to join {tournament.name}. "
        "Review the application to approve or reject it.",
        approvals_link(tournament.id),
    )


def create_team_registration(
    db: Session,
    current_user_id: int,
    data: RegistrationCreate,
) -> Registration:
    """Create a tournament registration for the authenticated team captain."""

    if data.registration_type != RegistrationType.TEAM:
        raise BadRequestException(
            detail="Only team registration is allowed"
        )

    if data.team_id is None:
        raise BadRequestException(
            detail="team_id is required for team registration"
        )

    team = (
        db.query(Team)
        .filter(Team.id == data.team_id)
        .first()
    )

    if team is None:
        raise NotFoundException(detail="Team not found")

    if team.captain_id != current_user_id:
        raise ForbiddenException(
            detail="Only the team captain can register the team"
        )

    if team.status != TeamStatus.ACTIVE:
        raise BadRequestException(
            detail="Only active teams can register"
        )

    inactive_player = (
        db.query(Player)
        .filter(
            Player.team_id == team.id,
            Player.status != "active",
        )
        .first()
    )

    if inactive_player is not None:
        raise ConflictException(
            detail="Only active players can be added to a team"
        )


    validate_tournament_for_registration(
        db,
        data.tournament_id,
        expected_participation_type="team",
    )

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
    _notify_organiser_of_application(db, registration, team.name)

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

    if data.registration_type != RegistrationType.PLAYER:
        raise BadRequestException(
            detail="Only player registration is allowed"
        )

    player = (
        db.query(Player)
        .filter(Player.user_id == current_user_id)
        .first()
    )

    if player is None:
        raise NotFoundException(
            detail="Player profile not found"
        )

    validate_player_registration(
        db,
        data.tournament_id,
        player.id,
    )

    registration = Registration(
        tournament_id=data.tournament_id,
        team_id=None,
        player_id=player.id,
        registration_type=RegistrationType.PLAYER.value,
        status=RegistrationStatus.PENDING.value,
        note=data.note,
    )

    db.add(registration)
    _notify_organiser_of_application(
        db, registration, f"{player.first_name} {player.last_name}"
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictException(
            detail="Player is already registered for this tournament"
        )

    db.refresh(registration)

    return registration


def _ensure_tournament_owner(
    tournament: Tournament | None,
    organiser_id: int | None,
) -> None:
    """Reject organisers acting on a tournament they do not own.

    organiser_id is None only for internal callers that already enforce
    their own authorisation.
    """
    if organiser_id is None:
        return

    if tournament is None or tournament.organizer_id != organiser_id:
        raise ForbiddenException(detail="You do not own this tournament")


def _get_owned_registration(
    db: Session,
    registration_id: int,
    organiser_id: int | None,
) -> Registration:
    registration = (
        db.query(Registration)
        .filter(Registration.id == registration_id)
        .first()
    )

    if registration is None:
        raise NotFoundException(detail="Registration not found")

    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == registration.tournament_id)
        .first()
    )
    _ensure_tournament_owner(tournament, organiser_id)

    return registration


def update_registration_status(
    db: Session,
    registration_id: int,
    new_status: RegistrationStatus,
    *,
    organiser_id: int | None = None,
) -> Registration:
    """Update registration status and notify the participant if necessary."""

    registration = _get_owned_registration(db, registration_id, organiser_id)

    current_status = RegistrationStatus(registration.status)

    valid_transitions = {
        RegistrationStatus.PENDING: {
            RegistrationStatus.APPROVED,
            RegistrationStatus.REJECTED,
            RegistrationStatus.CANCELLED,
        },
        RegistrationStatus.APPROVED: set(),
        RegistrationStatus.REJECTED: set(),
        RegistrationStatus.CANCELLED: set(),
    }

    if new_status not in valid_transitions[current_status]:
        raise BadRequestException(
            detail=(
                f"Invalid status transition: "
                f"{current_status.value} to {new_status.value}"
            )
        )

    try:
        registration.status = new_status.value
        registration.reviewed_at = datetime.now(timezone.utc)

        notify_registration_status(db, registration)

        db.commit()
        db.refresh(registration)

    except Exception:
        db.rollback()
        raise

    return registration


def get_pending_registrations(
    db: Session,
    tournament_id: int,
    *,
    organiser_id: int | None = None,
) -> list[Registration]:
    """Retrieve all pending registrations for a tournament."""

    tournament = (
        db.query(Tournament)
        .filter(Tournament.id == tournament_id)
        .first()
    )

    if tournament is None:
        raise NotFoundException(detail="Tournament not found")

    _ensure_tournament_owner(tournament, organiser_id)

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
    *,
    organiser_id: int | None = None,
) -> Registration:
    """Approve a valid pending registration and notify the participant."""

    registration = _get_owned_registration(db, registration_id, organiser_id)

    if registration.status != RegistrationStatus.PENDING.value:
        raise BadRequestException(
            detail="Only pending registrations can be approved"
        )

    if registration.registration_type == RegistrationType.PLAYER.value:
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

    elif registration.registration_type == RegistrationType.TEAM.value:
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


    else:
        raise BadRequestException(
            detail="Invalid registration type"
        )

    try:
        if registration.registration_type == RegistrationType.TEAM.value:
            existing_tournament_team = (
                db.query(TournamentTeam)
                .filter(
                    TournamentTeam.tournament_id == registration.tournament_id,
                    TournamentTeam.team_id == registration.team_id,
                )
                .first()
            )

            if existing_tournament_team is None:
                db.add(
                    TournamentTeam(
                        tournament_id=registration.tournament_id,
                        team_id=registration.team_id,
                    )
                )
                db.flush()

        registration.status = RegistrationStatus.APPROVED.value
        registration.reviewed_at = datetime.now(timezone.utc)

        if registration.registration_type == RegistrationType.TEAM.value:
            existing_link = (
                db.query(TournamentTeam)
                .filter(
                    TournamentTeam.tournament_id == registration.tournament_id,
                    TournamentTeam.team_id == registration.team_id,
                )
                .first()
            )

            if existing_link is None:
                db.add(
                    TournamentTeam(
                        tournament_id=registration.tournament_id,
                        team_id=registration.team_id,
                    )
                )

        notify_registration_status(db, registration)

        db.commit()
        db.refresh(registration)

    except Exception:
        db.rollback()
        raise

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

    if registration.status != RegistrationStatus.PENDING.value:
        raise BadRequestException(
            detail="Only pending registrations can be updated"
        )

    if registration.registration_type == RegistrationType.PLAYER.value:
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

    elif registration.registration_type == RegistrationType.TEAM.value:
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

    if data.note is not None:
        registration.note = data.note

    db.commit()
    db.refresh(registration)

    return registration


def reject_registration(
    db: Session,
    registration_id: int,
    *,
    organiser_id: int | None = None,
) -> Registration:
    """Reject a pending registration and notify the participant."""

    registration = _get_owned_registration(db, registration_id, organiser_id)

    if registration.status != RegistrationStatus.PENDING.value:
        raise BadRequestException(
            detail="Only pending registrations can be rejected"
        )

    try:
        registration.status = RegistrationStatus.REJECTED.value
        registration.reviewed_at = datetime.now(timezone.utc)

        notify_registration_status(db, registration)

        db.commit()
        db.refresh(registration)

    except Exception:
        db.rollback()
        raise

    return registration


def get_my_registrations(
    db: Session,
    current_user_id: int,
    role: str,
) -> list[Registration]:
    """Return registrations belonging to the authenticated user."""

    if role not in ("player", "captain"):
        raise ForbiddenException(
            detail="You are not allowed to view these registrations"
        )

    conditions = []

    # Registrations for teams this user captains.
    team_ids = select(Team.id).where(Team.captain_id == current_user_id)
    conditions.append(Registration.team_id.in_(team_ids))

    # The user's own player registrations.
    player = (
        db.query(Player)
        .filter(Player.user_id == current_user_id)
        .first()
    )
    if player is not None:
        conditions.append(
            and_(
                Registration.registration_type == RegistrationType.PLAYER.value,
                Registration.player_id == player.id,
            )
        )

    return (
        db.query(Registration)
        .filter(or_(*conditions))
        .order_by(Registration.registered_at.desc())
        .all()
    )
