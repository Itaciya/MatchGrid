from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_access.base import Base


class TournamentTeam(Base):
    __tablename__ = "tournament_teams"
    __table_args__ = (
        UniqueConstraint(
        "tournament_id",
        "team_id",
        name="uq_tournament_team",
    ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    tournament_id: Mapped[int] = mapped_column(
        ForeignKey("tournaments.id"),
        nullable=False,
        index=True,
    )

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"),
        nullable=False,
        index=True,
    )

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    tournament = relationship(
        "Tournament",
        backref="tournament_teams",
    )

    team = relationship(
        "Team",
        backref="tournament_teams",
    )