"""Replace player is_active with status

Revision ID: 4c53852896e9
Revises: 2621c27349e7
Create Date: 2026-10-02 13:54:41.746548

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4c53852896e9"
down_revision: Union[str, Sequence[str], None] = "2621c27349e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "players",
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
            server_default="active",
        ),
    )

    op.drop_column("players", "is_active")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "players",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.drop_column("players", "status")