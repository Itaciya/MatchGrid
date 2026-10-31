"""add tournament participation type

Revision ID: 7a91c4e2b630
Revises: 01602e68d923
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7a91c4e2b630"
down_revision: Union[str, Sequence[str], None] = "01602e68d923"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tournaments",
        sa.Column(
            "participation_type",
            sa.String(length=20),
            nullable=False,
            server_default="team",
        ),
    )
    op.create_index(
        op.f("ix_tournaments_participation_type"),
        "tournaments",
        ["participation_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_tournaments_participation_type"),
        table_name="tournaments",
    )
    op.drop_column("tournaments", "participation_type")
