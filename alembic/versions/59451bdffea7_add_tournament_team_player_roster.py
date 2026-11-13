"""add tournament team player roster

Revision ID: 59451bdffea7
Revises: 19ccad0473fd
Create Date: 2026-11-10 00:54:52.503027

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '59451bdffea7'
down_revision: Union[str, Sequence[str], None] = '19ccad0473fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Create the referenced unique constraint BEFORE the composite foreign key.
    op.create_unique_constraint(
        'uq_tournament_team_id_pair',
        'tournament_teams',
        ['tournament_id', 'id'],
    )

    op.create_table(
        'tournament_team_players',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tournament_id', sa.Integer(), nullable=False),
        sa.Column('tournament_team_id', sa.Integer(), nullable=False),
        sa.Column('player_id', sa.Integer(), nullable=False),
        sa.Column('added_by_user_id', sa.Integer(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['added_by_user_id'],
            ['users.id'],
        ),
        sa.ForeignKeyConstraint(
            ['player_id'],
            ['players.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['tournament_id', 'tournament_team_id'],
            ['tournament_teams.tournament_id', 'tournament_teams.id'],
            name='fk_tournament_team_player_tournament_team',
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tournament_id',
            'player_id',
            name='uq_tournament_player',
        ),
    )

    op.create_index(
        op.f('ix_tournament_team_players_added_by_user_id'),
        'tournament_team_players',
        ['added_by_user_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_tournament_team_players_id'),
        'tournament_team_players',
        ['id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_tournament_team_players_player_id'),
        'tournament_team_players',
        ['player_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_tournament_team_players_tournament_id'),
        'tournament_team_players',
        ['tournament_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_tournament_team_players_tournament_team_id'),
        'tournament_team_players',
        ['tournament_team_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Drop dependent table BEFORE dropping its referenced unique constraint.
    op.drop_table('tournament_team_players')

    op.drop_constraint(
        'uq_tournament_team_id_pair',
        'tournament_teams',
        type_='unique',
    )
