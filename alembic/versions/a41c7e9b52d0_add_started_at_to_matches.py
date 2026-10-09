"""add started_at to matches

Revision ID: a41c7e9b52d0
Revises: d3d14396792b
Create Date: 2026-10-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a41c7e9b52d0"
down_revision: Union[str, Sequence[str], None] = "d3d14396792b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "matches",
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column("matches", "started_at")
