"""description

Revision ID: 491191db46b7
Revises: 63ccfa1b49e8
Create Date: 2026-03-25 22:11:11.936622

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '491191db46b7'
down_revision: Union[str, Sequence[str], None] = '63ccfa1b49e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
