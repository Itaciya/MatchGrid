from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_access.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False
    )

    notification_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    __table_args__ = (
        Index(
            "ix_notifications_user_id_is_read",
            "user_id",
            "is_read",
        ),
    )

    user = relationship(
        "User",
        backref="notifications"
    )

