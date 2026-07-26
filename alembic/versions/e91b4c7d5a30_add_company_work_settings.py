"""add company work settings (digest hour, resolved cooldown)

Revision ID: e91b4c7d5a30
Revises: c7f5d1a8e402
Create Date: 2026-07-26 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e91b4c7d5a30'
down_revision: Union[str, None] = 'c7f5d1a8e402'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('companies', schema=None) as batch_op:
        batch_op.add_column(sa.Column('digest_hour', sa.Integer(), nullable=False, server_default='8'))
        batch_op.add_column(
            sa.Column('resolved_cooldown_days', sa.Integer(), nullable=False, server_default='7')
        )


def downgrade() -> None:
    with op.batch_alter_table('companies', schema=None) as batch_op:
        batch_op.drop_column('resolved_cooldown_days')
        batch_op.drop_column('digest_hour')
