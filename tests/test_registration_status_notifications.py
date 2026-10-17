
from datetime import datetime, timezone
from uuid import uuid4

from app.modules.notification.models.notification import Notification
from app.modules.player_team.models.player import Player
from app.modules.player_team.models.team import Team
from app.modules.registration.models.registration import Registration
from app.modules.registration.schemas.registration import RegistrationStatus
from app.modules.registration.services.registration_service import (
    approve_registration,
    reject_registration,
)
from app.modules.tournament.models.tournament import Tournament
from app.modules.user.models import User


def create_registration_data(db, registration_type="player"):
    """Create the user, tournament and participant for a notification test."""

    user = User(
        email=f"status_notification_{uuid4()}@example.com",
        password_hash="test_hash",
        role="player",
    )
    db.add(user)
    db.flush()

    tournament = Tournament(
        name=f"Notification Tournament {uuid4()}",
        description="Registration status notification test",
        format="league",
        start_date=datetime(2027, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2027, 1, 31, tzinfo=timezone.utc),
        status="upcoming",
        organizer_id=user.id,
    )
    db.add(tournament)
    db.flush()

    if registration_type == "player":
        team = Team(
            name=f"Notification Team {uuid4()}",
            captain_id=user.id,
        )
        db.add(team)
        db.flush()

        player = Player(
            user_id=user.id,
            team_id=team.id,
            first_name="Test",
            last_name="Player",
            status="active",
        )
        db.add(player)
        db.flush()

        registration = Registration(
            tournament_id=tournament.id,
            player_id=player.id,
            team_id=None,
            registration_type="player",
            status="pending",
        )
    else:
        team = Team(
            name=f"Notification Team {uuid4()}",
            captain_id=user.id,
        )
        db.add(team)
        db.flush()

        registration = Registration(
            tournament_id=tournament.id,
            team_id=team.id,
            player_id=None,
            registration_type="team",
            status="pending",
        )

    db.add(registration)
    db.commit()
    db.refresh(registration)

    return user, tournament, registration


def test_approving_registration_creates_notification(db):
    user, tournament, registration = create_registration_data(db)

    approve_registration(db, registration.id)

    notification = (
        db.query(Notification)
        .filter(
            Notification.user_id == user.id,
            Notification.notification_type == "registration_status",
        )
        .first()
    )

    assert notification is not None
    assert tournament.name in notification.content
    assert "approved" in notification.content
    assert notification.is_read is False


def test_rejecting_registration_creates_notification(db):
    user, tournament, registration = create_registration_data(db)

    reject_registration(db, registration.id)

    notification = (
        db.query(Notification)
        .filter(
            Notification.user_id == user.id,
            Notification.notification_type == "registration_status",
        )
        .first()
    )

    assert notification is not None
    assert tournament.name in notification.content
    assert "rejected" in notification.content
    assert notification.is_read is False


def test_team_registration_notification_goes_to_captain(db):
    captain, tournament, registration = create_registration_data(
        db,
        registration_type="team",
    )

    approve_registration(db, registration.id)

    notification = (
        db.query(Notification)
        .filter(
            Notification.user_id == captain.id,
            Notification.notification_type == "registration_status",
        )
        .first()
    )

    assert notification is not None
    assert tournament.name in notification.content
    assert "approved" in notification.content


def test_approved_registration_cannot_be_approved_twice(db):
    user, _, registration = create_registration_data(db)

    approve_registration(db, registration.id)

    first_count = (
        db.query(Notification)
        .filter(
            Notification.user_id == user.id,
            Notification.notification_type == "registration_status",
        )
        .count()
    )

    # The service should reject a second approval of an already approved registration.
    from app.core.exceptions import BadRequestException

    try:
        approve_registration(db, registration.id)
    except BadRequestException:
        pass
    else:
        raise AssertionError("A second approval should be rejected")

    second_count = (
        db.query(Notification)
        .filter(
            Notification.user_id == user.id,
            Notification.notification_type == "registration_status",
        )
        .count()
    )

    assert first_count == 1
    assert second_count == 1
    assert registration.status == RegistrationStatus.APPROVED.value

def test_notification_failure_rolls_back_registration_status(db, monkeypatch):
    from unittest.mock import patch

    from app.modules.registration.services import registration_service

    _, _, registration = create_registration_data(db)

    original_status = registration.status

    with patch.object(
        registration_service,
        "notify_registration_status",
        side_effect=RuntimeError("Simulated notification failure"),
    ):
        try:
            approve_registration(db, registration.id)
        except RuntimeError as exc:
            assert str(exc) == "Simulated notification failure"
        else:
            raise AssertionError("Expected notification failure")

    db.expire_all()
    refreshed_registration = (
        db.query(Registration)
        .filter(Registration.id == registration.id)
        .first()
    )

    assert refreshed_registration.status == original_status
