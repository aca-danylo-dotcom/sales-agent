"""add llm cache fields to message_drafts

Revision ID: b3a41c9d20f7
Revises: 95021f2e127e
Create Date: 2026-07-26 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3a41c9d20f7'
down_revision: Union[str, None] = '95021f2e127e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('message_drafts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('explanation_text', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('source_fingerprint', sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('message_drafts', schema=None) as batch_op:
        batch_op.drop_column('source_fingerprint')
        batch_op.drop_column('explanation_text')
