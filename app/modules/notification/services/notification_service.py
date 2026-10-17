
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.modules.notification.models.notification import Notification
from app.modules.notification.schemas.notification import NotificationCreate
from app.modules.user.models import User


def create_notification(
    db: Session,
    data: NotificationCreate,
) -> Notification:
    """Create a notification for an existing user."""

    user = (
        db.query(User)
        .filter(User.id == data.user_id)
        .first()
    )

    if user is None:
        raise NotFoundException(detail="Notification recipient not found")

    notification = Notification(
        user_id=user.id,
        notification_type=data.notification_type,
        content=data.content,
        is_read=False,
    )

    try:
        db.add(notification)
        db.commit()
        db.refresh(notification)
    except Exception:
        db.rollback()
        raise

    return notification
