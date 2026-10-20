
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.notification.services.notification_broadcast_service import (
    broadcast_notification,
)
from app.realtime.redis_pubsub import pubsub_manager



@pytest.mark.anyio
async def test_broadcast_notification_sends_to_intended_recipient():
    notification = MagicMock()
    notification.id = 12
    notification.user_id = 5
    notification.notification_type = "match_update"
    notification.content = "Your match has been updated."
    notification.is_read = False
    notification.created_at = datetime(2026, 10, 20, tzinfo=timezone.utc)

    with patch.object(
        pubsub_manager,
        "publish_event",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_publish:
        await broadcast_notification(notification)

        mock_publish.assert_awaited_once_with(
            {
                "type": "notification:new",
                "payload": {
                    "notification_id": 12,
                    "recipient_id": 5,
                    "title": "Match Update",
                    "message": "Your match has been updated.",
                    "notification_type": "match_update",
                    "is_read": False,
                    "created_at": "2026-10-20T00:00:00+00:00",
                },
            }
        )

@pytest.mark.anyio
async def test_create_and_broadcast_notification():
    from app.modules.notification.services.notification_broadcast_service import (
        create_and_broadcast_notification,
    )

    db = MagicMock()
    notification = MagicMock()
    data = MagicMock()

    with (
        patch(
            "app.modules.notification.services.notification_broadcast_service.create_notification",
            return_value=notification,
        ) as mock_create,
        patch(
            "app.modules.notification.services.notification_broadcast_service.broadcast_notification",
            new_callable=AsyncMock,
        ) as mock_broadcast,
    ):
        result = await create_and_broadcast_notification(db, data)

        assert result is notification
        mock_create.assert_called_once_with(db, data)
        mock_broadcast.assert_awaited_once_with(notification)