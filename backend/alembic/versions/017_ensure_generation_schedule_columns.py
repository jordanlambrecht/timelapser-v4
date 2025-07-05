"""Ensure generation_schedule columns exist in cameras and timelapses tables

Revision ID: 017_ensure_generation_schedule_columns
Revises: 016_unify_stopped_completed_status
Create Date: 2025-01-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "017_fix_generation_schedule"
down_revision: Union[str, None] = "016_unify_stopped_completed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Ensure generation_schedule columns exist in cameras and timelapses tables.
    This fixes the database error where queries expect these columns to exist.
    """
    
    # Check if generation_schedule column exists in cameras table, add if missing
    connection = op.get_bind()
    
    # Check cameras table
    cameras_result = connection.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'cameras' 
        AND column_name = 'generation_schedule'
    """))
    
    if not cameras_result.fetchone():
        # Column doesn't exist, add it
        op.add_column(
            "cameras",
            sa.Column(
                "generation_schedule",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )
        print("Added generation_schedule column to cameras table")
    else:
        print("generation_schedule column already exists in cameras table")
    
    # Check timelapses table
    timelapses_result = connection.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'timelapses' 
        AND column_name = 'generation_schedule'
    """))
    
    if not timelapses_result.fetchone():
        # Column doesn't exist, add it
        op.add_column(
            "timelapses",
            sa.Column(
                "generation_schedule",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
        )
        print("Added generation_schedule column to timelapses table")
    else:
        print("generation_schedule column already exists in timelapses table")


def downgrade() -> None:
    """
    Remove generation_schedule columns if they were added by this migration.
    Note: This only removes if the columns were added by this specific migration.
    """
    # This is a repair migration, so we don't remove columns in downgrade
    # as they might have been created by migration 010 originally
    pass