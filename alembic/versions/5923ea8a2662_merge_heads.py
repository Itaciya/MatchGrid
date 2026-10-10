"""merge heads

Revision ID: 5923ea8a2662
Revises: c8e3f1a97b25, 908b6483adb0
Create Date: 2026-10-09 16:38:00.573396

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5923ea8a2662'
down_revision: Union[str, Sequence[str], None] = ('c8e3f1a97b25', '908b6483adb0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
