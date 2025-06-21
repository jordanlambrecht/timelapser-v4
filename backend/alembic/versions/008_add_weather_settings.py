"""Add OpenWeather integration settings

Revision ID: 008_add_weather_settings
Revises: 007_corruption_detection
Create Date: 2025-06-21 15:00:00.000000

"""

from alembic import op

# revision identifiers
revision = "008_add_weather_settings"
down_revision = "007_corruption_detection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add weather integration settings"""

    # Insert new weather settings with default values
    op.execute(
        """
        INSERT INTO settings (key, value) VALUES 
        ('latitude', ''),
        ('longitude', ''),
        ('weather_enabled', 'false'),
        ('sunrise_sunset_enabled', 'false'),
        ('sunrise_offset_minutes', '0'),
        ('sunset_offset_minutes', '0'),
        ('current_temp', ''),
        ('current_weather_icon', ''),
        ('current_weather_description', ''),
        ('weather_date_fetched', ''),
        ('sunrise_timestamp', ''),
        ('sunset_timestamp', '')
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    """Remove weather integration settings"""

    # Remove the weather settings we added
    op.execute(
        """
        DELETE FROM settings WHERE key IN (
            'latitude',
            'longitude',
            'weather_enabled',
            'sunrise_sunset_enabled',
            'sunrise_offset_minutes',
            'sunset_offset_minutes',
            'current_temp',
            'current_weather_icon',
            'current_weather_description',
            'weather_date_fetched',
            'sunrise_timestamp',
            'sunset_timestamp'
        )
        """
    )
