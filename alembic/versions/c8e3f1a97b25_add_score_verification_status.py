"""add score verification status

Revision ID: c8e3f1a97b25
Revises: a41c7e9b52d0
Create Date: 2026-10-09 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8e3f1a97b25"
down_revision: Union[str, Sequence[str], None] = "a41c7e9b52d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "scores",
        sa.Column(
            "verification_status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column(
        "scores",
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "scores",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Carry existing data over before the consistency constraint exists.
    op.execute(
        "UPDATE scores SET verification_status = 'verified' WHERE is_verified"
    )

    op.create_index(
        "ix_scores_reviewed_by_id",
        "scores",
        ["reviewed_by_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_scores_reviewed_by_id",
        "scores",
        "users",
        ["reviewed_by_id"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_scores_verification_status",
        "scores",
        "verification_status IN ('pending', 'verified', 'rejected')",
    )
    op.create_check_constraint(
        "ck_scores_is_verified_matches_status",
        "scores",
        "is_verified = (verification_status = 'verified')",
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_constraint(
        "ck_scores_is_verified_matches_status", "scores", type_="check"
    )
    op.drop_constraint("ck_scores_verification_status", "scores", type_="check")
    op.drop_constraint("fk_scores_reviewed_by_id", "scores", type_="foreignkey")
    op.drop_index("ix_scores_reviewed_by_id", table_name="scores")
    op.drop_column("scores", "reviewed_at")
    op.drop_column("scores", "reviewed_by_id")
    op.drop_column("scores", "verification_status")
