"""add tournament registration period

Revision ID: 4da12b903404
Revises: 7a91c4e2b630
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4da12b903404"
down_revision: Union[str, Sequence[str], None] = "7a91c4e2b630"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tournaments",
        sa.Column("registration_open_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tournaments",
        sa.Column("registration_close_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        """
        UPDATE tournaments
        SET registration_open_at = created_at,
            registration_close_at = start_date
        """
    )

    op.alter_column(
        "tournaments",
        "registration_open_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.alter_column(
        "tournaments",
        "registration_close_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("tournaments", "registration_close_at")
    op.drop_column("tournaments", "registration_open_at")
