"""create match table

Revision ID: 4403f43fca30
Revises: 903be7bd2230
Create Date: 2026-09-27 00:31:57.160239

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4403f43fca30"
down_revision: Union[str, Sequence[str], None] = "903be7bd2230"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tournament_id", sa.Integer(), nullable=False),
        sa.Column("team_a_id", sa.Integer(), nullable=False),
        sa.Column("team_b_id", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["team_a_id"],
            ["teams.id"],
        ),
        sa.ForeignKeyConstraint(
            ["team_b_id"],
            ["teams.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tournament_id"],
            ["tournaments.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_matches_id"),
        "matches",
        ["id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_matches_tournament_id"),
        "matches",
        ["tournament_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_matches_team_a_id"),
        "matches",
        ["team_a_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_matches_team_b_id"),
        "matches",
        ["team_b_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_matches_team_b_id"),
        table_name="matches",
    )
    op.drop_index(
        op.f("ix_matches_team_a_id"),
        table_name="matches",
    )
    op.drop_index(
        op.f("ix_matches_tournament_id"),
        table_name="matches",
    )
    op.drop_index(
        op.f("ix_matches_id"),
        table_name="matches",
    )
    op.drop_table("matches")