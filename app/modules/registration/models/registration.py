from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_access.base import Base


class Registration(Base):
    __tablename__ = "registrations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    tournament_id: Mapped[int] = mapped_column(
        ForeignKey("tournaments.id"),
        nullable=False,
        index=True,
    )

    team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id"),
        nullable=True,
        index=True,
    )

    player_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id"),
        nullable=True,
        index=True,
    )

    registration_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )

    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    tournament = relationship(
        "Tournament",
        backref="registrations",
    )

    team = relationship(
        "Team",
        backref="registrations",
    )

    player = relationship(
        "Player",
        backref="registrations",
    )

    __table_args__ = (
        UniqueConstraint(
            "tournament_id",
            "team_id",
            "player_id",
            name="uq_registration_tournament_participant",
        ),
    )

    @property
    def team_name(self) -> str | None:
        return self.team.name if self.team else None

    @property
    def player_name(self) -> str | None:
        if self.player is None:
            return None
        return f"{self.player.first_name} {self.player.last_name}".strip()

    @property
    def tournament_name(self) -> str | None:
        return self.tournament.name if self.tournament else None
