"""add tournament category

Revision ID: 01602e68d923
Revises: eb4813031282
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "01602e68d923"
down_revision: Union[str, Sequence[str], None] = "eb4813031282"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tournaments",
        sa.Column(
            "category",
            sa.String(length=20),
            nullable=False,
            server_default="sports",
        ),
    )
    op.create_index(
        op.f("ix_tournaments_category"),
        "tournaments",
        ["category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tournaments_category"), table_name="tournaments")
    op.drop_column("tournaments", "category")