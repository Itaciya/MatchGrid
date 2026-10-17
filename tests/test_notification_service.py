
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import NotFoundException
from app.modules.notification.models.notification import Notification
from app.modules.notification.schemas.notification import NotificationCreate
from app.modules.notification.services.notification_service import (
    create_notification,
)


def test_create_notification_success():
    db = MagicMock()
    user = MagicMock()
    user.id = 5

    db.query.return_value.filter.return_value.first.return_value = user

    data = NotificationCreate(
        user_id=5,
        notification_type="tournament_update",
        content="Your tournament schedule has changed.",
    )

    result = create_notification(db, data)

    assert isinstance(result, Notification)
    assert result.user_id == 5
    assert result.notification_type == "tournament_update"
    assert result.content == "Your tournament schedule has changed."
    assert result.is_read is False

    db.add.assert_called_once_with(result)
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(result)


def test_create_notification_rejects_missing_user():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    data = NotificationCreate(
        user_id=999,
        notification_type="tournament_update",
        content="Your tournament schedule has changed.",
    )

    with pytest.raises(NotFoundException):
        create_notification(db, data)

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_create_notification_rolls_back_on_database_error():
    db = MagicMock()
    user = MagicMock()
    user.id = 5

    db.query.return_value.filter.return_value.first.return_value = user
    db.commit.side_effect = RuntimeError("Database commit failed")

    data = NotificationCreate(
        user_id=5,
        notification_type="tournament_update",
        content="Your tournament schedule has changed.",
    )

    with pytest.raises(RuntimeError, match="Database commit failed"):
        create_notification(db, data)

    db.rollback.assert_called_once()
