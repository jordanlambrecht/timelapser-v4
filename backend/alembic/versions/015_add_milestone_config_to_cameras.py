"""
Add milestone_config column back to cameras table

Revision ID: 015_milestone_config
Revises: 014_populate_defaults
Create Date: 2025-06-28 15:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "015_milestone_config"
down_revision = "014_populate_defaults"
branch_labels = None
depends_on = None


def upgrade():
    # No-op: milestone_config already exists. This migration is now a placeholder to maintain revision chain integrity.
    pass


def downgrade():
    # No-op: Do not drop milestone_config, as this migration is a placeholder.
    pass
