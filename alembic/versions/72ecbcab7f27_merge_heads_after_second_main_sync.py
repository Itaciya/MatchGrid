"""merge heads after second main sync

Revision ID: 72ecbcab7f27
Revises: fb2a04903ea2, aff276b95d35
Create Date: 2026-10-10 03:37:23.766442

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '72ecbcab7f27'
down_revision: Union[str, Sequence[str], None] = ('fb2a04903ea2', 'aff276b95d35')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
