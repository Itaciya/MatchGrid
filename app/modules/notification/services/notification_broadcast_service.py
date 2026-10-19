
from app.modules.notification.models.notification import Notification
from app.realtime.connection_manager import manager
from app.modules.notification.schemas.notification import NotificationCreate
from app.modules.notification.services.notification_service import create_notification

async def broadcast_notification(notification: Notification) -> None:
    """Send a new notification only to its intended recipient."""

    await manager.send_personal_message(
        {
            "type": "notification:new",
            "payload": {
                "notification_id": notification.id,
                "recipient_id": notification.user_id,
                "title": notification.notification_type.replace("_", " ").title(),
                "message": notification.content,
                "notification_type": notification.notification_type,
                "is_read": notification.is_read,
                "created_at": (
                    notification.created_at.isoformat()
                    if notification.created_at is not None
                    else None
                ),
            },
        },
        notification.user_id,
    )
def schedule_notification_broadcast(notification: Notification) -> bool:
    """Schedule a notification broadcast from a background thread."""
    return manager.schedule_personal_message(
        {
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
        },
        notification.user_id,
    )
async def create_and_broadcast_notification(db, data: NotificationCreate):
    notification = create_notification(db, data)
    await broadcast_notification(notification)
    return notification
