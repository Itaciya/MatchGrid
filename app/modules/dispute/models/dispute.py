from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_access.base import Base


class Dispute(Base):
    __tablename__ = "disputes"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id"),
        nullable=False,
        index=True
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending"
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

    match = relationship(
        "Match",
        backref="disputes"
    )

    user = relationship(
        "User",
        backref="disputes"
    )