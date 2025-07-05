"""
Add missing automation/corruption columns to cameras table for migration compatibility

Revision ID: 013a_add_missing_camera_columns
Revises: 013_fix_video_automation_mode_data
Create Date: 2025-06-28 20:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "013a_add_missing_camera_columns"
down_revision = "013_fix_automation_data"
branch_labels = None
depends_on = None


def upgrade():
    # No-op: milestone_config already exists. This migration is now a placeholder to maintain revision chain integrity.
    pass


def downgrade():
    # No-op: Do not drop milestone_config, as this migration is a placeholder.
    pass
