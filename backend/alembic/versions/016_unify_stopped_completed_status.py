"""Unify stopped and completed status

Revision ID: 016_unify_stopped_completed
Revises: 015_add_milestone_config_to_cameras
Create Date: 2025-06-30

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "016_unify_stopped_completed"
down_revision = "4b55598c5213"
branch_labels = None
depends_on = None


def upgrade():
    """Update all 'stopped' statuses to 'completed' for consistency"""
    # Update timelapse statuses
    op.execute(
        """
        UPDATE timelapses 
        SET status = 'completed' 
        WHERE status = 'stopped'
    """
    )

    # Update the check constraint to remove 'stopped' as a valid status
    op.execute(
        """
        ALTER TABLE timelapses 
        DROP CONSTRAINT IF EXISTS timelapses_status_check
    """
    )

    op.execute(
        """
        ALTER TABLE timelapses 
        ADD CONSTRAINT timelapses_status_check 
        CHECK (status IN ('running', 'paused', 'completed', 'archived'))
    """
    )


def downgrade():
    """Revert by adding 'stopped' back as a valid status"""
    # Remove the updated constraint
    op.execute(
        """
        ALTER TABLE timelapses 
        DROP CONSTRAINT IF EXISTS timelapses_status_check
    """
    )

    # Add back the original constraint with 'stopped'
    op.execute(
        """
        ALTER TABLE timelapses 
        ADD CONSTRAINT timelapses_status_check 
        CHECK (status IN ('running', 'paused', 'stopped', 'completed', 'archived'))
    """
    )

    # Note: We don't revert the data changes since we can't distinguish
    # which 'completed' statuses were originally 'stopped'
