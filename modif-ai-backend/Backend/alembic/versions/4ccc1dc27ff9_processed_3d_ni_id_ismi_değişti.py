"""processed_3d ni id ismi değişti

Revision ID: 4ccc1dc27ff9
Revises: e48c98389a35
Create Date: 2026-04-02 08:35:37.593761

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4ccc1dc27ff9'
down_revision: Union[str, Sequence[str], None] = 'e48c98389a35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
