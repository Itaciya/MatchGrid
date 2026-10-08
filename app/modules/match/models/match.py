from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_access.base import Base


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    tournament_id: Mapped[int] = mapped_column(
        ForeignKey("tournaments.id"),
        nullable=False,
        index=True
    )

    match_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    round_id: Mapped[int | None] = mapped_column(
        ForeignKey("tournament_rounds.id"),
        nullable=True,
        index=True
    )

    team_a_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id"),
        nullable=True,
        index=True
    )

    team_b_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id"),
        nullable=True,
        index=True
    )

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="scheduled",
        index=True
    )

    winner_next_match_id: Mapped[int | None] = mapped_column(
        ForeignKey("matches.id"),
        nullable=True,
        index=True
    )

    loser_next_match_id: Mapped[int | None] = mapped_column(
        ForeignKey("matches.id"),
        nullable=True,
        index=True
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
            "tournament_id",
            "match_number",
            name="uq_match_tournament_match_number",
        ),
        CheckConstraint(
            "team_a_id != team_b_id",
            name="ck_match_team_a_not_team_b",
        ),
    )

    tournament = relationship(
        "Tournament",
        backref="matches"
    )

    round = relationship(
        "TournamentRound",
        back_populates="matches"
    )

    team_a = relationship(
        "Team",
        foreign_keys=[team_a_id],
        backref="home_matches"
    )

    team_b = relationship(
        "Team",
        foreign_keys=[team_b_id],
        backref="away_matches"
    )

    winner_next_match = relationship(
        "Match",
        foreign_keys=[winner_next_match_id],
        remote_side=[id],
        backref="winner_previous_matches"
    )

    loser_next_match = relationship(
        "Match",
        foreign_keys=[loser_next_match_id],
        remote_side=[id],
        backref="loser_previous_matches"
    )

    score = relationship(
        "Score",
        back_populates="match",
        uselist=False
    )