"""Add log_level column to presets table.

Revision ID: 002
Revises: 001
Create Date: 2025-12-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add log_level column to presets table."""
    # Add log_level column with default value "INFO"
    op.add_column(
        'presets',
        sa.Column('log_level', sa.String(20), nullable=False, server_default='INFO')
    )


def downgrade() -> None:
    """Remove log_level column from presets table."""
    op.drop_column('presets', 'log_level')
