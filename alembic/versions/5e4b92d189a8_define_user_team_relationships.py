"""define user team relationships

Revision ID: 5e4b92d189a8
Revises: 48ec4764e4d2
Create Date: 2026-09-27 14:22:42.198576

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e4b92d189a8'
down_revision: Union[str, Sequence[str], None] = '48ec4764e4d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'players',
        sa.Column('team_id', sa.Integer(), nullable=False),
    )

    op.create_index(
        op.f('ix_players_team_id'),
        'players',
        ['team_id'],
        unique=False,
    )

    op.create_foreign_key(
        'fk_players_team_id_teams',
        'players',
        'teams',
        ['team_id'],
        ['id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'fk_players_team_id_teams',
        'players',
        type_='foreignkey',
    )

    op.drop_index(
        op.f('ix_players_team_id'),
        table_name='players',
    )

    op.drop_column(
        'players',
        'team_id',
    )