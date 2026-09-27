"""update registration relationships

Revision ID: 9d0b2b8f89ae
Revises: d2d642ae976e
Create Date: 2026-09-27 17:34:08.045606

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d0b2b8f89ae"
down_revision: Union[str, Sequence[str], None] = "d2d642ae976e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "registrations",
        sa.Column("team_id", sa.Integer(), nullable=True),
    )

    op.add_column(
        "registrations",
        sa.Column("player_id", sa.Integer(), nullable=True),
    )

    op.drop_index(
        "ix_registrations_participant_id",
        table_name="registrations",
    )

    op.drop_constraint(
        "uq_registration_tournament_participant",
        "registrations",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_registration_tournament_participant",
        "registrations",
        ["tournament_id", "team_id", "player_id"],
    )

    op.create_index(
        "ix_registrations_player_id",
        "registrations",
        ["player_id"],
        unique=False,
    )

    op.create_index(
        "ix_registrations_team_id",
        "registrations",
        ["team_id"],
        unique=False,
    )

    op.drop_constraint(
        "registrations_participant_id_fkey",
        "registrations",
        type_="foreignkey",
    )

    op.create_foreign_key(
        "fk_registrations_player_id_players",
        "registrations",
        "players",
        ["player_id"],
        ["id"],
    )

    op.create_foreign_key(
        "fk_registrations_team_id_teams",
        "registrations",
        "teams",
        ["team_id"],
        ["id"],
    )

    op.drop_column(
        "registrations",
        "participant_id",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "registrations",
        sa.Column(
            "participant_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.drop_constraint(
        "fk_registrations_player_id_players",
        "registrations",
        type_="foreignkey",
    )

    op.drop_constraint(
        "fk_registrations_team_id_teams",
        "registrations",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_registrations_team_id",
        table_name="registrations",
    )

    op.drop_index(
        "ix_registrations_player_id",
        table_name="registrations",
    )

    op.drop_constraint(
        "uq_registration_tournament_participant",
        "registrations",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_registration_tournament_participant",
        "registrations",
        ["tournament_id", "participant_id"],
    )

    op.create_index(
        "ix_registrations_participant_id",
        "registrations",
        ["participant_id"],
        unique=False,
    )

    op.create_foreign_key(
        "registrations_participant_id_fkey",
        "registrations",
        "users",
        ["participant_id"],
        ["id"],
    )

    op.drop_column(
        "registrations",
        "player_id",
    )

    op.drop_column(
        "registrations",
        "team_id",
    )