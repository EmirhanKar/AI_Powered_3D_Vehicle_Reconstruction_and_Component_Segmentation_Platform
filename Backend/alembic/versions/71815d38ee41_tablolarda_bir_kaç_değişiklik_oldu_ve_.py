"""tablolarda bir kaç değişiklik oldu ve 2d processed tablosu eklendi

Revision ID: 71815d38ee41
Revises: dfec3697b442
Create Date: 2026-04-02 08:22:59.045927

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71815d38ee41'
down_revision: Union[str, Sequence[str], None] = 'dfec3697b442'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
