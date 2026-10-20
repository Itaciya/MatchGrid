
from app.modules.notification.models.notification import Notification
from app.modules.notification.schemas.notification import NotificationCreate
from app.modules.notification.services.notification_service import create_notification
from app.realtime.redis_pubsub import pubsub_manager


def notification_event(notification: Notification) -> dict:
    """Build the real-time event for one notification recipient."""
    return {
        "type": "notification:new",
        "payload": {
            "notification_id": notification.id,
            "recipient_id": notification.user_id,
            "title": notification.notification_type.replace(
                "_", " "
            ).title(),
            "message": notification.content,
            "notification_type": notification.notification_type,
            "is_read": notification.is_read,
            "created_at": (
                notification.created_at.isoformat()
                if notification.created_at is not None
                else None
            ),
        },
    }


async def broadcast_notification(notification: Notification) -> None:
    """Publish a notification for delivery to its intended recipient."""
    await pubsub_manager.publish_event(notification_event(notification))


def schedule_notification_broadcast(notification: Notification) -> bool:
    """Schedule notification publishing from a background thread."""
    return pubsub_manager.schedule_event(notification_event(notification))


async def create_and_broadcast_notification(
    db,
    data: NotificationCreate,
):
    """Persist a notification and publish its real-time event."""
    notification = create_notification(db, data)
    await broadcast_notification(notification)
    return notification
