"""add venue model

Revision ID: d3d14396792b
Revises: 39dcef4c70e3
Create Date: 2026-10-08 23:37:07.250327

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d3d14396792b"
down_revision: Union[str, Sequence[str], None] = "39dcef4c70e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "venues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "name",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column(
            "location",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "capacity",
            sa.Integer(),
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
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_venues_id",
        "venues",
        ["id"],
        unique=False,
    )

    op.create_index(
        "ix_venues_name",
        "venues",
        ["name"],
        unique=True,
    )

    op.add_column(
        "matches",
        sa.Column(
            "venue_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_matches_venue_id",
        "matches",
        ["venue_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_matches_venue_id",
        "matches",
        "venues",
        ["venue_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_constraint(
        "fk_matches_venue_id",
        "matches",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_matches_venue_id",
        table_name="matches",
    )

    op.drop_column(
        "matches",
        "venue_id",
    )

    op.drop_index(
        "ix_venues_name",
        table_name="venues",
    )

    op.drop_index(
        "ix_venues_id",
        table_name="venues",
    )

    op.drop_table("venues")