"""merge heads after main sync

Revision ID: 6af4d0587b83
Revises: 3fcbc80e8f32, b51c3d381779
Create Date: 2026-10-09 21:49:21.030110

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6af4d0587b83'
down_revision: Union[str, Sequence[str], None] = ('3fcbc80e8f32', 'b51c3d381779')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
