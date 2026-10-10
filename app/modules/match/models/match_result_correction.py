from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.data_access.base import Base


class MatchResultCorrection(Base):
    """Audit trail: one row per correction of a finalized result (SCRUM-151)."""

    __tablename__ = "match_result_corrections"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_result_id: Mapped[int] = mapped_column(
        ForeignKey("match_results.id", ondelete="CASCADE"), index=True
    )
    corrected_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    old_team_a_score: Mapped[int] = mapped_column(Integer)
    old_team_b_score: Mapped[int] = mapped_column(Integer)
    new_team_a_score: Mapped[int] = mapped_column(Integer)
    new_team_b_score: Mapped[int] = mapped_column(Integer)
    old_outcome: Mapped[str] = mapped_column(String(20))
    new_outcome: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(500))
    corrected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
