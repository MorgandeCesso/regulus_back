"""add chat and message models

Revision ID: daa7d77858d3
Revises: 4fa3945e67cc
Create Date: 2025-01-08 17:33:14.499173

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'daa7d77858d3'
down_revision: Union[str, None] = '4fa3945e67cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('chats', sa.Column('thread_id', sa.String(length=500), nullable=True))
    op.alter_column('chats', 'title',
               existing_type=sa.VARCHAR(length=100),
               nullable=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('chats', 'title',
               existing_type=sa.VARCHAR(length=100),
               nullable=False)
    op.drop_column('chats', 'thread_id')
    # ### end Alembic commands ###