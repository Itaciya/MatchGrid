from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_access.base import Base


class OfficialAssignment(Base):
    __tablename__ = "official_assignments"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id"),
        nullable=False,
        index=True
    )

    official_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    assignment_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active"
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
        UniqueConstraint(
            "match_id",
            "official_id",
            "assignment_type",
            name="uq_official_assignment_match_official_type",
        ),
    )
    match = relationship(
        "Match",
        backref="official_assignments"
    )

    official = relationship(
        "User",
        backref="official_assignments"
    )

