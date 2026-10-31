from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data_access.base import Base


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        unique=True,
        index=True,
    )

    category: Mapped[str] = mapped_column(
    String(20),
    nullable=False,
    default="sports",
    server_default="sports",
    index=True,
    )

    participation_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="team",
        server_default="team",
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    format: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    format_config: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    registration_open_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    registration_close_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="upcoming",
        index=True,
    )

    fixtures_published: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    organizer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Tournament picture
    image_data: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
    )

    image_content_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    @property
    def image_url(self) -> str | None:
        if self.image_content_type:
            return f"/tournaments/{self.id}/image"
        return None

    organizer = relationship(
        "User",
        backref="tournaments",
    )