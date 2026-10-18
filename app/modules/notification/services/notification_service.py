
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

def get_user_notifications(
    db: Session,
    user_id: int,
    unread_only: bool = False,
) -> list[Notification]:
    """Retrieve notifications belonging to one user."""
    query = db.query(Notification).filter(
        Notification.user_id == user_id
    )

    if unread_only:
        query = query.filter(Notification.is_read.is_(False))

    return (
        query
        .order_by(Notification.created_at.desc())
        .all()
    )

def mark_notification_as_read(
    db: Session,
    notification_id: int,
    user_id: int,
) -> Notification:
    """Mark a notification as read if it belongs to the user."""

    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        .first()
    )

    if notification is None:
        raise NotFoundException(detail="Notification not found")

    notification.is_read = True

    try:
        db.commit()
        db.refresh(notification)
    except Exception:
        db.rollback()
        raise

    return notification



def update_notification_read_status(
    db: Session,
    notification_id: int,
    user_id: int,
    is_read: bool,
) -> Notification:
    """Update read/unread status for the notification owner only."""

    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        .first()
    )

    if notification is None:
        raise NotFoundException(detail="Notification not found")

    notification.is_read = is_read

    try:
        db.commit()
        db.refresh(notification)
    except Exception:
        db.rollback()
        raise

    return notification