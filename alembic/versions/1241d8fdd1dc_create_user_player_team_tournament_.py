"""create user player team tournament tables

Revision ID: 1241d8fdd1dc
Revises:
Create Date: 2026-09-26 20:39:59.551467
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1241d8fdd1dc"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_players_id", "players", ["id"], unique=False)
    op.create_index(
        "ix_players_user_id",
        "players",
        ["user_id"],
        unique=True,
    )

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("captain_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
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
        sa.ForeignKeyConstraint(["captain_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_teams_captain_id",
        "teams",
        ["captain_id"],
        unique=False,
    )
    op.create_index("ix_teams_id", "teams", ["id"], unique=False)
    op.create_index(
        "ix_teams_name",
        "teams",
        ["name"],
        unique=True,
    )

    op.create_table(
        "tournaments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("format", sa.String(length=50), nullable=False),
        sa.Column(
            "start_date",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "end_date",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("organizer_id", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["organizer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_tournaments_id",
        "tournaments",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_tournaments_name",
        "tournaments",
        ["name"],
        unique=True,
    )
    op.create_index(
        "ix_tournaments_organizer_id",
        "tournaments",
        ["organizer_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tournaments_organizer_id",
        table_name="tournaments",
    )
    op.drop_index(
        "ix_tournaments_name",
        table_name="tournaments",
    )
    op.drop_index(
        "ix_tournaments_id",
        table_name="tournaments",
    )
    op.drop_table("tournaments")

    op.drop_index(
        "ix_teams_name",
        table_name="teams",
    )
    op.drop_index(
        "ix_teams_id",
        table_name="teams",
    )
    op.drop_index(
        "ix_teams_captain_id",
        table_name="teams",
    )
    op.drop_table("teams")

    op.drop_index(
        "ix_players_user_id",
        table_name="players",
    )
    op.drop_index(
        "ix_players_id",
        table_name="players",
    )
    op.drop_table("players")

    op.drop_index(
        "ix_users_email",
        table_name="users",
    )
    op.drop_index(
        "ix_users_id",
        table_name="users",
    )
    op.drop_table("users")