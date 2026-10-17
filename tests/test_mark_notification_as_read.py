
from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user, get_db
from app.main import app
from app.modules.notification.models.notification import Notification
from app.modules.notification.services.notification_service import (
    mark_notification_as_read,
)
from app.modules.user.models import User


def test_mark_notification_as_read_updates_status():
    db = MagicMock()

    notification = MagicMock(spec=Notification)
    notification.id = 1
    notification.user_id = 10
    notification.is_read = False

    query = db.query.return_value
    query.filter.return_value.first.return_value = notification

    result = mark_notification_as_read(
        db=db,
        notification_id=1,
        user_id=10,
    )

    assert result.is_read is True
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(notification)


def test_mark_notification_as_read_returns_notification():
    db = MagicMock()

    notification = MagicMock(spec=Notification)
    notification.id = 5
    notification.user_id = 10
    notification.notification_type = "upcoming_match_reminder"
    notification.content = "Your match starts soon."
    notification.is_read = False
    notification.created_at = datetime(2026, 10, 18, tzinfo=timezone.utc)
    notification.updated_at = datetime(2026, 10, 18, tzinfo=timezone.utc)

    query = db.query.return_value
    query.filter.return_value.first.return_value = notification

    user = MagicMock(spec=User)
    user.id = 10

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    try:
        with TestClient(app) as client:
            response = client.patch("/notifications/5/read")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 5
        assert data["user_id"] == 10
        assert data["is_read"] is True
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_cannot_mark_another_users_notification_as_read():
    db = MagicMock()

    query = db.query.return_value
    query.filter.return_value.first.return_value = None

    user = MagicMock(spec=User)
    user.id = 10

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    try:
        with TestClient(app) as client:
            response = client.patch("/notifications/99/read")

        assert response.status_code == 404
        db.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_mark_notification_as_read_requires_authentication():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)

    with TestClient(app) as client:
        response = client.patch("/notifications/1/read")

    assert response.status_code in (401, 403)
