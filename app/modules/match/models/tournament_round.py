from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_access.base import Base


class TournamentRound(Base):
    __tablename__ = "tournament_rounds"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    tournament_id: Mapped[int] = mapped_column(
        ForeignKey("tournaments.id"),
        nullable=False,
        index=True
    )

    round_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    bracket_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="main"
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

    tournament = relationship(
        "Tournament",
        backref="rounds"
    )

    matches = relationship(
        "Match",
        back_populates="round"
    )

    __table_args__ = (
        UniqueConstraint(
            "tournament_id",
            "round_number",
            "bracket_type",
            name="uq_tournament_round_order",
        ),
    )
