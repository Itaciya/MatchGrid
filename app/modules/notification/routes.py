
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.data_access.database import get_db

from app.modules.notification.schemas.notification import (
    NotificationReadStatusUpdate,
    NotificationResponse,
)
from app.modules.notification.services.notification_service import (
    get_user_notifications,
    mark_notification_as_read,
    update_notification_read_status,
)

from app.modules.user.models import User


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


@router.get(
    "/",
    response_model=list[NotificationResponse],
)
def read_my_notifications(
    unread_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve notifications belonging only to the authenticated user."""
    return get_user_notifications(
        db=db,
        user_id=current_user.id,
        unread_only=unread_only,
    )

@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
)
def mark_my_notification_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark the authenticated user's notification as read."""
    return mark_notification_as_read(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id,
    )

@router.patch(
    "/{notification_id}/status",
    response_model=NotificationResponse,
)
def update_my_notification_status(
    notification_id: int,
    status_data: NotificationReadStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update read/unread status of the authenticated user's notification."""
    return update_notification_read_status(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id,
        is_read=status_data.is_read,
    )
