
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from app.modules.match.models.match import Match
from app.modules.notification.models.notification import Notification
from app.modules.player_team.models.team import Team
from app.modules.registration.models.registration import Registration
from app.modules.player_team.models.player import Player

import pytest

from app.modules.notification.services.upcoming_match_reminder_service import (
    generate_upcoming_match_reminders,
)


def test_reminder_rejects_non_positive_reminder_minutes():
    db = MagicMock()

    with pytest.raises(ValueError, match="reminder_minutes"):
        generate_upcoming_match_reminders(
            db,
            now=datetime(2099, 1, 1, tzinfo=timezone.utc),
            reminder_minutes=0,
        )

    db.query.assert_not_called()


def test_reminder_rejects_non_positive_window_minutes():
    db = MagicMock()

    with pytest.raises(ValueError, match="window_minutes"):
        generate_upcoming_match_reminders(
            db,
            now=datetime(2099, 1, 1, tzinfo=timezone.utc),
            reminder_minutes=60,
            window_minutes=0,
        )

    db.query.assert_not_called()


def test_reminder_returns_zero_when_no_match_is_due():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []

    result = generate_upcoming_match_reminders(
        db,
        now=datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc),
        reminder_minutes=60,
        window_minutes=1,
    )

    assert result == 0
    db.commit.assert_called_once()
    db.rollback.assert_not_called()


def test_reminder_uses_configured_time_window():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []

    now = datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc)

    result = generate_upcoming_match_reminders(
        db,
        now=now,
        reminder_minutes=30,
        window_minutes=5,
    )

    assert result == 0

   
    db.query.assert_called()
    db.commit.assert_called_once()
def test_reminder_skips_existing_duplicate_notification():
    db = MagicMock()

    now = datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc)

    match = MagicMock()
    match.id = 123
    match.match_number = 1
    match.tournament_id = 10
    match.team_a_id = 20
    match.team_b_id = 21
    match.scheduled_at = now + timedelta(minutes=60)

    team_a = MagicMock()
    team_a.id = 20
    team_a.captain_id = 30

    team_b = MagicMock()
    team_b.id = 21
    team_b.captain_id = 31

    # Return the match, then its teams, then no registrations.
    match_query = MagicMock()
    match_query.filter.return_value.all.return_value = [match]

    team_query = MagicMock()
    team_query.filter.return_value.all.return_value = [team_a, team_b]

    registration_query = MagicMock()
    registration_query.join.return_value.filter.return_value.all.return_value = []

    notification_query = MagicMock()
    notification_query.filter.return_value.first.return_value = object()

    def query_side_effect(model):
        if model is Match:
            return match_query
        if model is Team:
            return team_query
        if model is Registration:
            return registration_query
        if model is Notification:
            return notification_query
        return MagicMock()

    db.query.side_effect = query_side_effect

    result = generate_upcoming_match_reminders(
        db,
        now=now,
        reminder_minutes=60,
        window_minutes=1,
    )

    assert result == 0
    db.add.assert_not_called()
    db.commit.assert_called_once()
    db.rollback.assert_not_called()



def test_reminder_creates_notification_for_team_captains():
    db = MagicMock()

    now = datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc)

    match = MagicMock()
    match.id = 456
    match.match_number = 2
    match.tournament_id = 11
    match.team_a_id = 40
    match.team_b_id = 41
    match.scheduled_at = now + timedelta(minutes=60)

    team_a = MagicMock()
    team_a.id = 40
    team_a.captain_id = 50

    team_b = MagicMock()
    team_b.id = 41
    team_b.captain_id = 51

    match_query = MagicMock()
    match_query.filter.return_value.all.return_value = [match]

    team_query = MagicMock()
    team_query.filter.return_value.all.return_value = [team_a, team_b]

    registration_query = MagicMock()
    registration_query.join.return_value.filter.return_value.all.return_value = []

    notification_query = MagicMock()
    notification_query.filter.return_value.first.return_value = None

    def query_side_effect(model):
        if model is Match:
            return match_query
        if model is Team:
            return team_query
        if model is Registration:
            return registration_query
        if model is Notification:
            return notification_query
        return MagicMock()

    db.query.side_effect = query_side_effect

    result = generate_upcoming_match_reminders(
        db,
        now=now,
        reminder_minutes=60,
        window_minutes=1,
    )

    assert result == 2
    assert db.add.call_count == 2
    db.commit.assert_called_once()

    notifications = [
        call.args[0] for call in db.add.call_args_list
    ]

    assert {n.user_id for n in notifications} == {50, 51}

    for notification in notifications:
        assert notification.notification_type == "upcoming_match_reminder"
        assert "Match ID 456" in notification.content
        assert "Match 2" in notification.content
        assert notification.is_read is False


def test_reminder_includes_approved_players_from_participating_teams():
    db = MagicMock()

    now = datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc)

    match = MagicMock()
    match.id = 789
    match.match_number = 3
    match.tournament_id = 12
    match.team_a_id = 60
    match.team_b_id = 61
    match.scheduled_at = now + timedelta(minutes=60)

    team_a = MagicMock()
    team_a.id = 60
    team_a.captain_id = 70

    team_b = MagicMock()
    team_b.id = 61
    team_b.captain_id = 71

    registration = MagicMock()
    registration.player_id = 80

    player = MagicMock()
    player.id = 80
    player.user_id = 90
    player.team_id = 60

    match_query = MagicMock()
    match_query.filter.return_value.all.return_value = [match]

    team_query = MagicMock()
    team_query.filter.return_value.all.return_value = [team_a, team_b]

    registration_query = MagicMock()
    registration_query.join.return_value.filter.return_value.all.return_value = [
        registration
    ]

    player_query = MagicMock()
    player_query.filter.return_value.first.return_value = player

    notification_query = MagicMock()
    notification_query.filter.return_value.first.return_value = None

    def query_side_effect(model):
        if model is Match:
            return match_query
        if model is Team:
            return team_query
        if model is Registration:
            return registration_query
        if model is Player:
            return player_query
        if model is Notification:
            return notification_query
        return MagicMock()

    db.query.side_effect = query_side_effect

    result = generate_upcoming_match_reminders(
        db,
        now=now,
        reminder_minutes=60,
        window_minutes=1,
    )

    assert result == 3
    assert db.add.call_count == 3

    notifications = [
        call.args[0] for call in db.add.call_args_list
    ]
    recipient_ids = {notification.user_id for notification in notifications}

    assert recipient_ids == {70, 71, 90}

def test_reminder_deduplicates_same_user_as_captain_and_player():
    db = MagicMock()

    now = datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc)

    match = MagicMock()
    match.id = 987
    match.match_number = 4
    match.tournament_id = 13
    match.team_a_id = 70
    match.team_b_id = 71
    match.scheduled_at = now + timedelta(minutes=60)

    team_a = MagicMock()
    team_a.id = 70
    team_a.captain_id = 100

    team_b = MagicMock()
    team_b.id = 71
    team_b.captain_id = 101

    registration = MagicMock()
    registration.player_id = 80

    player = MagicMock()
    player.id = 80
    player.user_id = 100
    player.team_id = 70

    match_query = MagicMock()
    match_query.filter.return_value.all.return_value = [match]

    team_query = MagicMock()
    team_query.filter.return_value.all.return_value = [team_a, team_b]

    registration_query = MagicMock()
    registration_query.join.return_value.filter.return_value.all.return_value = [
        registration
    ]

    player_query = MagicMock()
    player_query.filter.return_value.first.return_value = player

    notification_query = MagicMock()
    notification_query.filter.return_value.first.return_value = None

    def query_side_effect(model):
        if model is Match:
            return match_query
        if model is Team:
            return team_query
        if model is Registration:
            return registration_query
        if model is Player:
            return player_query
        if model is Notification:
            return notification_query
        return MagicMock()

    db.query.side_effect = query_side_effect

    result = generate_upcoming_match_reminders(
        db,
        now=now,
        reminder_minutes=60,
        window_minutes=1,
    )

    notifications = [
        call.args[0] for call in db.add.call_args_list
    ]
    recipient_ids = [notification.user_id for notification in notifications]

    assert result == 2
    assert len(recipient_ids) == 2
    assert set(recipient_ids) == {100, 101}
