"""add snoozed_until to recommendations

Revision ID: c7f5d1a8e402
Revises: b3a41c9d20f7
Create Date: 2026-07-26 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7f5d1a8e402'
down_revision: Union[str, None] = 'b3a41c9d20f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('recommendations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('snoozed_until', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('recommendations', schema=None) as batch_op:
        batch_op.drop_column('snoozed_until')
