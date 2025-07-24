"""Add weather data to images table

Revision ID: 033_add_weather_to_images
Revises: 032_create_overlay_system
Create Date: 2025-01-11 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = '033_add_weather_to_images'
down_revision = '032_create_overlay_system'
branch_labels = None
depends_on = None


def upgrade():
    """Add weather data fields to images table for historical weather accuracy in overlays."""
    
    print("🌤️  Adding weather data fields to images table...")
    
    try:
        # Add weather data columns to images table
        op.add_column('images', sa.Column('weather_temperature', sa.Float, nullable=True))
        op.add_column('images', sa.Column('weather_conditions', sa.String(255), nullable=True))
        op.add_column('images', sa.Column('weather_icon', sa.String(50), nullable=True))
        op.add_column('images', sa.Column('weather_fetched_at', sa.TIMESTAMP(timezone=True), nullable=True))
        
        print("✅ Weather data fields added to images table")
        
        # Create index for weather-based queries
        op.create_index('idx_images_weather_fetched_at', 'images', ['weather_fetched_at'])
        op.create_index('idx_images_weather_conditions', 'images', ['weather_conditions'])
        
        print("✅ Weather data indexes created")
        
        # Add comment to document the purpose
        connection = op.get_bind()
        connection.execute(text("""
            COMMENT ON COLUMN images.weather_temperature IS 'Temperature in Celsius at the time of image capture';
            COMMENT ON COLUMN images.weather_conditions IS 'Weather description (e.g., sunny, cloudy, rainy) at capture time';
            COMMENT ON COLUMN images.weather_icon IS 'OpenWeather icon code for weather conditions';
            COMMENT ON COLUMN images.weather_fetched_at IS 'Timestamp when weather data was recorded for this image';
        """))
        
        print("✅ Added column documentation")
        print("🌤️  Weather integration migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during weather fields migration: {e}")
        raise


def downgrade():
    """Remove weather data fields from images table."""
    
    print("🔄 Removing weather data fields from images table...")
    
    try:
        # Drop indexes first
        op.drop_index('idx_images_weather_conditions', table_name='images')
        op.drop_index('idx_images_weather_fetched_at', table_name='images')
        print("✅ Weather data indexes removed")
        
        # Remove weather columns
        op.drop_column('images', 'weather_fetched_at')
        op.drop_column('images', 'weather_icon')
        op.drop_column('images', 'weather_conditions')
        op.drop_column('images', 'weather_temperature')
        print("✅ Weather data fields removed from images table")
        
        print("🔄 Weather integration migration rollback completed!")
        
    except Exception as e:
        print(f"❌ Error during weather fields rollback: {e}")
        raise