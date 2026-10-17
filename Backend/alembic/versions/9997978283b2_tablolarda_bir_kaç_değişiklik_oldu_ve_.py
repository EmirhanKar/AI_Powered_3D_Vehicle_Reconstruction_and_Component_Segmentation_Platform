"""tablolarda bir kaç değişiklik oldu ve 2d processed tablosu eklendi

Revision ID: 9997978283b2
Revises: 71815d38ee41
Create Date: 2026-04-02 08:25:45.451974

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9997978283b2'
down_revision: Union[str, Sequence[str], None] = '71815d38ee41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
