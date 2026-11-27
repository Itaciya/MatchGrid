"""add notification links and tournament followers

Revision ID: b8e2f4c1d903
Revises: 7a1d2e9c4b10
Create Date: 2026-11-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8e2f4c1d903'
down_revision: Union[str, Sequence[str], None] = '7a1d2e9c4b10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Where the notification should take the user in the app, e.g.
    # "#/verify/12". Nullable: older notifications have no link.
    op.add_column(
        'notifications',
        sa.Column('link', sa.String(length=255), nullable=True),
    )

    op.create_table(
        'tournament_followers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tournament_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['tournament_id'], ['tournaments.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tournament_id', 'user_id', name='uq_tournament_follower'
        ),
    )
    op.create_index(
        'ix_tournament_followers_user_id', 'tournament_followers', ['user_id']
    )


def downgrade() -> None:
    op.drop_index(
        'ix_tournament_followers_user_id', table_name='tournament_followers'
    )
    op.drop_table('tournament_followers')
    op.drop_column('notifications', 'link')
