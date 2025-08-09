"""Add max database logs setting

Revision ID: 041_add_max_database_logs_setting
Revises: 040_add_scheduled_jobs_table
Create Date: 2025-08-07 12:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "041_max_db_logs"
down_revision = "39d14c373e84"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add max_database_logs setting to control log count limits."""

    # Add the setting if it doesn't exist
    op.execute(
        """
        INSERT INTO settings (key, value, created_at, updated_at)
        SELECT 'max_database_logs', '50000', NOW(), NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM settings WHERE key = 'max_database_logs'
        )
    """
    )


def downgrade() -> None:
    """Remove max_database_logs setting."""

    op.execute("DELETE FROM settings WHERE key = 'max_database_logs'")
