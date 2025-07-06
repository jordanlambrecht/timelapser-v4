"""Separate database and file logging settings

Revision ID: 021_separate_logging_systems
Revises: 020_weather_single_row_table
Create Date: 2025-07-06 12:00:00.000000

"""

from alembic import op

# revision identifiers
revision = "021_separate_logging_systems"
down_revision = "020_weather_single_row_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Separate database and file logging settings"""

    # Add new separated logging settings
    op.execute(
        """
        INSERT INTO settings (key, value) VALUES 
        ('db_log_retention_days', '30'),
        ('db_log_level', 'info'),
        ('file_log_retention_days', '7'),  
        ('file_log_level', 'info')
        ON CONFLICT (key) DO NOTHING
        """
    )

    # Copy existing values to maintain user preferences
    op.execute(
        """
        -- Copy current log_retention_days to both new settings if they don't exist
        INSERT INTO settings (key, value) 
        SELECT 'db_log_retention_days', value 
        FROM settings 
        WHERE key = 'log_retention_days'
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
        
        INSERT INTO settings (key, value) 
        SELECT 'file_log_retention_days', '7'  -- Default file logs to shorter retention
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
        
        -- Copy current log_level to both new settings  
        INSERT INTO settings (key, value) 
        SELECT 'db_log_level', value 
        FROM settings 
        WHERE key = 'log_level'
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
        
        INSERT INTO settings (key, value) 
        SELECT 'file_log_level', value 
        FROM settings 
        WHERE key = 'log_level'  
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
        """
    )

    # Remove redundant debug logging setting (being replaced by separate log levels)
    op.execute(
        """
        DELETE FROM settings WHERE key = 'enable_debug_logging'
        """
    )

    print("✅ Separated logging systems: database logs vs file logs")
    print("📊 Database logs: for application events (captures, errors, etc.)")
    print("📁 File logs: for system debugging (worker processes, etc.)")


def downgrade() -> None:
    """Restore unified logging settings"""

    # Restore enable_debug_logging setting
    op.execute(
        """
        INSERT INTO settings (key, value) VALUES 
        ('enable_debug_logging', 'false')
        ON CONFLICT (key) DO NOTHING
        """
    )

    # Remove separated logging settings
    op.execute(
        """
        DELETE FROM settings WHERE key IN (
            'db_log_retention_days',
            'db_log_level', 
            'file_log_retention_days',
            'file_log_level'
        )
        """
    )

    print("⚠️  Restored unified logging settings (not recommended)")
