from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_access.base import Base

OUTCOME_TEAM_A_WIN = "team_a_win"
OUTCOME_TEAM_B_WIN = "team_b_win"
OUTCOME_DRAW = "draw"


class MatchResult(Base):
    """The official, finalized result of a match (SCRUM-145 / SCRUM-150).

    One row per match. The unique match_id is what prevents duplicate
    finalization, even under concurrent requests.
    """

    __tablename__ = "match_results"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id"),
        nullable=False,
        unique=True,
        index=True
    )

    outcome: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    winner_team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id"),
        nullable=True,
        index=True
    )

    loser_team_id: Mapped[int | None] = mapped_column(
        ForeignKey("teams.id"),
        nullable=True,
        index=True
    )

    team_a_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    team_b_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    finalized_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    finalized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
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
        CheckConstraint(
            "outcome IN ('team_a_win', 'team_b_win', 'draw')",
            name="ck_match_results_outcome",
        ),
        CheckConstraint(
            "(outcome = 'draw' AND winner_team_id IS NULL "
            "AND loser_team_id IS NULL) "
            "OR (outcome <> 'draw' AND winner_team_id IS NOT NULL "
            "AND loser_team_id IS NOT NULL "
            "AND winner_team_id <> loser_team_id)",
            name="ck_match_results_winner_loser_consistent",
        ),
        CheckConstraint(
            "(outcome = 'team_a_win' AND team_a_score > team_b_score) "
            "OR (outcome = 'team_b_win' AND team_b_score > team_a_score) "
            "OR (outcome = 'draw' AND team_a_score = team_b_score)",
            name="ck_match_results_outcome_matches_scores",
        ),
    )

    match = relationship("Match")
