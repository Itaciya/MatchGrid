
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.modules.notification.schemas.notification import (
    NotificationCreate,
    NotificationReadStatusUpdate,
    NotificationResponse,
    NotificationUpdate,
)


def test_notification_create_accepts_valid_data():
    notification = NotificationCreate(
        user_id=1,
        notification_type="match_update",
        content="Your match has been updated",
    )

    assert notification.user_id == 1
    assert notification.notification_type == "match_update"
    assert notification.content == "Your match has been updated"


def test_notification_create_rejects_missing_required_fields():
    with pytest.raises(ValidationError):
        NotificationCreate(user_id=1)


@pytest.mark.parametrize("user_id", [0, -1, True, "1"])
def test_notification_create_rejects_invalid_user_id(user_id):
    with pytest.raises(ValidationError):
        NotificationCreate(
            user_id=user_id,
            notification_type="match_update",
            content="Match updated",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("notification_type", ""),
        ("notification_type", "   "),
        ("content", ""),
        ("content", "   "),
    ],
)
def test_notification_create_rejects_empty_text(field, value):
    data = {
        "user_id": 1,
        "notification_type": "match_update",
        "content": "Match updated",
    }
    data[field] = value

    with pytest.raises(ValidationError):
        NotificationCreate(**data)


def test_notification_create_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        NotificationCreate(
            user_id=1,
            notification_type="match_update",
            content="Match updated",
            unexpected="not allowed",
        )


def test_notification_create_rejects_long_notification_type():
    with pytest.raises(ValidationError):
        NotificationCreate(
            user_id=1,
            notification_type="x" * 51,
            content="Match updated",
        )


def test_notification_update_accepts_read_status():
    update = NotificationUpdate(is_read=True)

    assert update.is_read is True


def test_notification_update_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        NotificationUpdate(unexpected="not allowed")


def test_read_status_update_requires_boolean():
    status = NotificationReadStatusUpdate(is_read=True)

    assert status.is_read is True

    with pytest.raises(ValidationError):
        NotificationReadStatusUpdate()


def test_notification_response_accepts_valid_data():
    now = datetime.now(timezone.utc)

    response = NotificationResponse(
        id=1,
        user_id=2,
        notification_type="match_update",
        content="Match updated",
        is_read=False,
        created_at=now,
        updated_at=now,
    )

    assert response.id == 1
    assert response.user_id == 2
    assert response.is_read is False
    assert response.created_at == now
