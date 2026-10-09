"""merge fixture and dispute migration heads

Revision ID: b51c3d381779
Revises: ba9ac504a6f6, 908b6483adb0, c8e3f1a97b25
Create Date: 2026-10-09 18:01:12.475907

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b51c3d381779'
down_revision: Union[str, Sequence[str], None] = ('ba9ac504a6f6', '908b6483adb0', 'c8e3f1a97b25')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
