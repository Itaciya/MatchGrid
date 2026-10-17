
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user, get_db
from app.main import app
from app.modules.notification.models.notification import Notification
from app.modules.notification.services.notification_service import (
    get_user_notifications,
)
from app.modules.user.models import User


def test_get_user_notifications_returns_only_requested_users_records():
    db = MagicMock()
    first_notification = MagicMock(spec=Notification)
    first_notification.user_id = 10
    first_notification.is_read = False

    query = db.query.return_value
    query.filter.return_value.order_by.return_value.all.return_value = [
        first_notification
    ]

    result = get_user_notifications(db, user_id=10)

    assert result == [first_notification]
    db.query.assert_called_once_with(Notification)


def test_get_user_notifications_applies_unread_filter():
    db = MagicMock()

    query = db.query.return_value
    query.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []

    result = get_user_notifications(
        db,
        user_id=10,
        unread_only=True,
    )

    assert result == []
    assert query.filter.call_count == 1
    query.filter.return_value.filter.assert_called_once()


def test_notifications_endpoint_returns_authenticated_users_notifications():
    user = MagicMock(spec=User)
    user.id = 10

    notification = Notification(
        user_id=10,
        notification_type="upcoming_match_reminder",
        content="Your match starts soon.",
        is_read=False,
        created_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
        updated_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
    )
    notification.id = 1

    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value.order_by.return_value.all.return_value = [
        notification
    ]

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    try:
        with TestClient(app) as client:
            response = client.get("/notifications/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["user_id"] == 10
        assert data[0]["notification_type"] == "upcoming_match_reminder"
        assert data[0]["content"] == "Your match starts soon."
        assert data[0]["is_read"] is False
        assert "created_at" in data[0]
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_notifications_endpoint_requires_authentication():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)

    with TestClient(app) as client:
        response = client.get("/notifications/")

    assert response.status_code in (401, 403)


def test_notifications_endpoint_supports_unread_only_filter():
    user = MagicMock(spec=User)
    user.id = 10

    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value.filter.return_value.order_by.return_value.all.return_value = []

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    try:
        with TestClient(app) as client:
            response = client.get("/notifications/?unread_only=true")

        assert response.status_code == 200
        assert response.json() == []
        assert query.filter.return_value.filter.called
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
