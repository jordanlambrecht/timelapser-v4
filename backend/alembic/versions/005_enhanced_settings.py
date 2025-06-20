"""Add enhanced logging and API key settings

Revision ID: 005_enhanced_settings
Revises: 004_video_gen_settings
Create Date: 2025-06-18 10:00:00.000000

"""

from alembic import op

# revision identifiers
revision = "005_enhanced_settings"
down_revision = "004_video_gen_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add new settings for enhanced logging and API key management"""

    # Insert new logging settings with default values
    op.execute(
        """
        INSERT INTO settings (key, value) VALUES 
        ('image_capture_type', 'JPG'),
        ('openweather_api_key_hash', ''),
        ('log_retention_days', '30'),
        ('max_log_file_size', '100'),
        ('enable_debug_logging', 'false'),
        ('log_level', 'info'),
        ('enable_log_rotation', 'true'),
        ('enable_log_compression', 'false'),
        ('max_log_files', '10')
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    """Remove enhanced settings"""

    # Remove the settings we added
    op.execute(
        """
        DELETE FROM settings WHERE key IN (
            'image_capture_type',
            'openweather_api_key_hash',
            'log_retention_days',
            'max_log_file_size',
            'enable_debug_logging',
            'log_level',
            'enable_log_rotation',
            'enable_log_compression',
            'max_log_files'
        )
        """
    )
