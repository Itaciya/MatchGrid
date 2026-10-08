"""add match number to matches

Revision ID: 39dcef4c70e3
Revises: 89fd60a36a22
Create Date: 2026-10-08 21:21:05.898616

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "39dcef4c70e3"
down_revision: Union[str, Sequence[str], None] = "89fd60a36a22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        "matches",
        sa.Column(
            "match_number",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.execute(
        sa.text(
            """
            WITH numbered_matches AS (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY tournament_id
                        ORDER BY id
                    ) AS generated_match_number
                FROM matches
            )
            UPDATE matches
            SET match_number = numbered_matches.generated_match_number
            FROM numbered_matches
            WHERE matches.id = numbered_matches.id
            """
        )
    )

    op.alter_column(
        "matches",
        "match_number",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.create_unique_constraint(
        "uq_match_tournament_match_number",
        "matches",
        ["tournament_id", "match_number"],
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_constraint(
        "uq_match_tournament_match_number",
        "matches",
        type_="unique",
    )

    op.drop_column(
        "matches",
        "match_number",
    )