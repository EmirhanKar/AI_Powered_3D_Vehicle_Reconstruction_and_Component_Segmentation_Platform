"""processed_3d ni id ismi değişti

Revision ID: e48c98389a35
Revises: dd75364bca1e
Create Date: 2026-04-02 08:32:20.562060

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e48c98389a35'
down_revision: Union[str, Sequence[str], None] = 'dd75364bca1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
