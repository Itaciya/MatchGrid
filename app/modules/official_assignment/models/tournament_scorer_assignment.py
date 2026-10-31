from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_access.base import Base


class TournamentScorerAssignment(Base):
    __tablename__ = "tournament_scorer_assignments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    tournament_id: Mapped[int] = mapped_column(
        ForeignKey("tournaments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    scorer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        default="active",
        server_default="active",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "tournament_id",
            "scorer_id",
            name="uq_tournament_scorer",
        ),
    )

    tournament = relationship("Tournament")
    scorer = relationship("User")
