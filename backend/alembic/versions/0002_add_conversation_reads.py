"""add conversation_reads table

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'conversation_reads',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('conversation_id', sa.Uuid(), nullable=False),
        sa.Column('last_read_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'conversation_id', name='pk_conversation_reads')
    )
    op.create_index(
        'ix_conversation_reads_user_conv',
        'conversation_reads',
        ['user_id', 'conversation_id'],
        unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_conversation_reads_user_conv', table_name='conversation_reads')
    op.drop_table('conversation_reads')
