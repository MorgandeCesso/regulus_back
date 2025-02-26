"""empty message

Revision ID: fc7169c109ea
Revises: 9cd29f903263
Create Date: 2025-01-05 17:01:50.527065

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fc7169c109ea'
down_revision: Union[str, None] = '9cd29f903263'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('messages', sa.Column('is_sent_by_bot', sa.Boolean(), nullable=False))
    op.add_column('users', sa.Column('refresh_token', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('hashed_password', sa.String(length=100), nullable=False))
    op.drop_column('users', 'password')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('password', sa.VARCHAR(length=100), autoincrement=False, nullable=False))
    op.drop_column('users', 'hashed_password')
    op.drop_column('users', 'refresh_token')
    op.drop_column('messages', 'is_sent_by_bot')
    # ### end Alembic commands ###
