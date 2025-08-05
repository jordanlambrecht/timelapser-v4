"""Fix absolute paths in database

Revision ID: 013_fix_absolute_paths
Revises: 012_fix_settings_structure
Create Date: 2025-06-23 16:40:00.000000

"""

from alembic import op

# revision identifiers
revision = "013_fix_absolute_paths"
down_revision = "012_fix_settings_table_structure"
branch_labels = None
depends_on = None


def upgrade():
    """Convert absolute paths to relative paths in database"""

    # Fix videos table - convert absolute to relative paths
    op.execute(
        """
        UPDATE videos
        SET file_path = REGEXP_REPLACE(file_path, '^.*/data/', 'data/')
        WHERE file_path LIKE '%/data/%' AND file_path NOT LIKE 'data/%'
    """
    )

    # Fix images table - convert absolute to relative paths
    op.execute(
        """
        UPDATE images
        SET file_path = REGEXP_REPLACE(file_path, '^.*/data/', 'data/')
        WHERE file_path LIKE '%/data/%' AND file_path NOT LIKE 'data/%'
    """
    )

    # Fix any thumbnail paths if they exist
    op.execute(
        """
        UPDATE images
        SET thumbnail_path = REGEXP_REPLACE(thumbnail_path, '^.*/data/', 'data/')
        WHERE thumbnail_path IS NOT NULL
        AND thumbnail_path LIKE '%/data/%'
        AND thumbnail_path NOT LIKE 'data/%'
    """
    )


def downgrade():
    """Cannot safely downgrade path conversions"""
    # Note: We cannot reliably convert relative paths back to absolute
    # as we don't know the original absolute base path
    pass
