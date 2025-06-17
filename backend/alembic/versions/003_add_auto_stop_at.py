"""Add auto_stop_at to timelapses table

Revision ID: 003_add_auto_stop_at
Revises: 002_create_settings_table
Create Date: 2025-06-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_add_auto_stop_at'
down_revision = '002_create_settings_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add auto_stop_at column to timelapses table
    op.add_column('timelapses', sa.Column('auto_stop_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Remove auto_stop_at column from timelapses table
    op.drop_column('timelapses', 'auto_stop_at')
