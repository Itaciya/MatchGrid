from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_access.base import Base


class Registration(Base):
    __tablename__ = "registrations"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    tournament_id: Mapped[int] = mapped_column(
        ForeignKey("tournaments.id"),
        nullable=False,
        index=True
    )

    participant_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    registration_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending"
    )

    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    tournament = relationship(
        "Tournament",
        backref="registrations"
    )

    participant = relationship(
        "User",
        backref="registrations"
    )

    __table_args__ = (
        UniqueConstraint(
            "tournament_id",
            "participant_id",
            name="uq_registration_tournament_participant"
        ),
    )