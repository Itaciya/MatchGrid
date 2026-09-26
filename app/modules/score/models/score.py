from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_access.base import Base


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

    match = relationship(
        "Match",
        backref="score"
    )