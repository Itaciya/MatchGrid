"""add venue created_by_id

Revision ID: 7a1d2e9c4b10
Revises: 5c343549f3c9
Create Date: 2026-11-24 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a1d2e9c4b10'
down_revision: Union[str, Sequence[str], None] = '5c343549f3c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: venues created before this change have no recorded owner.
    op.add_column(
        'venues',
        sa.Column('created_by_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_venues_created_by_id_users',
        'venues',
        'users',
        ['created_by_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_venues_created_by_id', 'venues', ['created_by_id']
    )


def downgrade() -> None:
    op.drop_index('ix_venues_created_by_id', table_name='venues')
    op.drop_constraint(
        'fk_venues_created_by_id_users', 'venues', type_='foreignkey'
    )
    op.drop_column('venues', 'created_by_id')
