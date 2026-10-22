
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user, get_db
from app.core.exceptions import NotFoundException
from app.main import app
from app.modules.notification.models.notification import Notification
from app.modules.notification.services.notification_service import (
    update_notification_read_status,
)
from app.modules.user.models import User


@pytest.mark.parametrize("is_read", [True, False])
def test_update_notification_read_status_updates_value(is_read):
    db = MagicMock()

    notification = MagicMock(spec=Notification)
    notification.id = 5
    notification.user_id = 10
    notification.is_read = not is_read

    query = db.query.return_value
    query.filter.return_value.first.return_value = notification

    result = update_notification_read_status(
        db=db,
        notification_id=5,
        user_id=10,
        is_read=is_read,
    )

    assert result.is_read is is_read
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(notification)


def test_cannot_update_another_users_notification_status():
    db = MagicMock()

    query = db.query.return_value
    query.filter.return_value.first.return_value = None

    with pytest.raises(NotFoundException):
        update_notification_read_status(
            db=db,
            notification_id=99,
            user_id=10,
            is_read=True,
        )

    db.commit.assert_not_called()


def test_status_endpoint_returns_updated_notification():
    db = MagicMock()

    notification = MagicMock(spec=Notification)
    notification.id = 5
    notification.user_id = 10
    notification.notification_type = "upcoming_match_reminder"
    notification.content = "Your match starts soon."
    notification.is_read = True
    notification.created_at = "2026-10-18T00:00:00+00:00"
    notification.updated_at = "2026-10-18T00:00:00+00:00"

    query = db.query.return_value
    query.filter.return_value.first.return_value = notification

    user = MagicMock(spec=User)
    user.id = 10

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    try:
        with TestClient(app) as client:
            response = client.patch(
                "/notifications/5/status",
                json={"is_read": True},
            )

        assert response.status_code == 200
        assert response.json()["is_read"] is True
        assert response.json()["id"] == 5
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_status_endpoint_requires_authentication():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)

    with TestClient(app) as client:
        response = client.patch(
            "/notifications/5/status",
            json={"is_read": False},
        )

    assert response.status_code in (401, 403)


def test_update_notification_read_status_rolls_back_and_reraises_db_error():
    db = MagicMock()

    notification = MagicMock(spec=Notification)
    notification.id = 5
    notification.user_id = 10
    notification.is_read = False

    query = db.query.return_value
    query.filter.return_value.first.return_value = notification
    db.commit.side_effect = RuntimeError("Database commit failed")

    with pytest.raises(RuntimeError, match="Database commit failed"):
        update_notification_read_status(
            db=db,
            notification_id=5,
            user_id=10,
            is_read=True,
        )

    db.rollback.assert_called_once()
