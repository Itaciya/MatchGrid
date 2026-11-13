from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.data_access.base import Base


class TournamentTeamPlayer(Base):
    __tablename__ = "tournament_team_players"

    __table_args__ = (
        UniqueConstraint(
            "tournament_id",
            "player_id",
            name="uq_tournament_player",
        ),
        ForeignKeyConstraint(
            ["tournament_id", "tournament_team_id"],
            ["tournament_teams.tournament_id", "tournament_teams.id"],
            name="fk_tournament_team_player_tournament_team",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    tournament_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    tournament_team_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    added_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
