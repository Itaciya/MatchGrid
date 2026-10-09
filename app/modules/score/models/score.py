import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_access.base import Base


class ScoreVerificationStatus(str, enum.Enum):
    """Review state of a submitted score.

    pending  -> verified | rejected   (organiser review)
    rejected -> pending               (only when the official corrects the score)
    verified is final.
    """

    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True
    )

    match_id: Mapped[int] = mapped_column(
        ForeignKey("matches.id"),
        nullable=False,
        index=True,
        unique=True
    )

    team_a_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    team_b_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    verification_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ScoreVerificationStatus.PENDING.value,
        server_default=ScoreVerificationStatus.PENDING.value
    )

    reviewed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
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
            "verification_status IN ('pending', 'verified', 'rejected')",
            name="ck_scores_verification_status",
        ),
        CheckConstraint(
            "is_verified = (verification_status = 'verified')",
            name="ck_scores_is_verified_matches_status",
        ),
    )

    match = relationship(
        "Match",
        back_populates="score"
    )
