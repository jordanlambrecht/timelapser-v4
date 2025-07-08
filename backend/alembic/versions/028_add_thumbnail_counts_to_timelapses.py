"""Add thumbnail count tracking to timelapses table

Revision ID: 028_thumbnail_counts
Revises: 027_thumb_perf_settings
Create Date: 2025-01-07 16:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "028_thumbnail_counts"
down_revision = "027_thumb_perf_settings"
branch_labels = None
depends_on = None


def upgrade():
    """Add thumbnail count tracking columns to timelapses table."""
    
    # Step 1: Add columns as nullable first
    op.add_column("timelapses", sa.Column("thumbnail_count", sa.Integer(), nullable=True))
    op.add_column("timelapses", sa.Column("small_count", sa.Integer(), nullable=True))
    
    # Step 2: Backfill existing data with actual counts from images table
    backfill_thumbnail_counts = """
        UPDATE timelapses 
        SET thumbnail_count = COALESCE(thumb_stats.thumbnail_count, 0),
            small_count = COALESCE(thumb_stats.small_count, 0)
        FROM (
            SELECT 
                i.timelapse_id,
                COUNT(CASE WHEN i.thumbnail_path IS NOT NULL AND i.thumbnail_path != '' THEN 1 END) as thumbnail_count,
                COUNT(CASE WHEN i.small_path IS NOT NULL AND i.small_path != '' THEN 1 END) as small_count
            FROM images i 
            WHERE i.timelapse_id IS NOT NULL 
            GROUP BY i.timelapse_id
        ) as thumb_stats
        WHERE timelapses.id = thumb_stats.timelapse_id;
    """
    
    op.execute(backfill_thumbnail_counts)
    
    # Step 3: Set default value for any rows that weren't updated
    op.execute("UPDATE timelapses SET thumbnail_count = 0 WHERE thumbnail_count IS NULL")
    op.execute("UPDATE timelapses SET small_count = 0 WHERE small_count IS NULL")
    
    # Step 4: Make columns NOT NULL with default values
    op.alter_column("timelapses", "thumbnail_count", nullable=False, server_default="0")
    op.alter_column("timelapses", "small_count", nullable=False, server_default="0")


def downgrade():
    """Remove thumbnail count tracking columns."""
    op.drop_column("timelapses", "small_count")
    op.drop_column("timelapses", "thumbnail_count")