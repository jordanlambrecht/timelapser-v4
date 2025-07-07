"""Add thumbnail performance configuration settings

Revision ID: 027_thumb_perf_settings  
Revises: 022_thumbnail_jobs
Create Date: 2025-07-07 00:30:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '027_thumb_perf_settings'
down_revision = '022_thumbnail_jobs'
branch_labels = None
depends_on = None


def upgrade():
    """Add thumbnail performance configuration settings."""
    
    # Insert thumbnail performance settings with default values
    op.execute(
        """
        INSERT INTO settings (key, value) VALUES 
        ('thumbnail_job_batch_size', '10'),
        ('thumbnail_worker_interval', '3'),
        ('thumbnail_max_retries', '3'),
        ('thumbnail_cleanup_hours', '24'),
        ('thumbnail_generation_enabled', 'true'),
        ('thumbnail_small_generation_mode', 'all'),
        ('thumbnail_purge_smalls_on_completion', 'false'),
        ('thumbnail_high_load_mode', 'false'),
        ('thumbnail_memory_limit_mb', '512'),
        ('thumbnail_concurrent_jobs', '3')
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade():
    """Remove thumbnail performance configuration settings."""
    
    # Remove the performance settings we added
    op.execute(
        """
        DELETE FROM settings WHERE key IN (
            'thumbnail_job_batch_size',
            'thumbnail_worker_interval',
            'thumbnail_max_retries',
            'thumbnail_cleanup_hours',
            'thumbnail_generation_enabled',
            'thumbnail_small_generation_mode',
            'thumbnail_purge_smalls_on_completion',
            'thumbnail_high_load_mode',
            'thumbnail_memory_limit_mb', 
            'thumbnail_concurrent_jobs'
        )
        """
    )