
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_access.base import Base


class DisputeStatusHistory(Base):
    """Record every status transition for a dispute."""

    __tablename__ = "dispute_status_history"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    dispute_id: Mapped[int] = mapped_column(
        ForeignKey("disputes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    previous_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    new_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    changed_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    dispute = relationship("Dispute", backref="status_history")
    user = relationship("User")
