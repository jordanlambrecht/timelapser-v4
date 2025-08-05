"""Create weather data table

Revision ID: 019_create_weather_table
Revises: 018_add_sse_events_table
Create Date: 2025-07-05 12:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.sql import func
from sqlalchemy import text
from alembic import op

# revision identifiers
revision = "019_create_weather_table"
down_revision = "018_add_sse_events_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create weather data table and migrate data from settings"""

    # Create the weather data table
    op.create_table(
        "weather_data",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("weather_date_fetched", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_temp", sa.Float(), nullable=True),
        sa.Column("current_weather_icon", sa.String(50), nullable=True),
        sa.Column("current_weather_description", sa.String(255), nullable=True),
        sa.Column("sunrise_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sunset_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("api_key_valid", sa.Boolean(), nullable=True, default=True),
        sa.Column("api_failing", sa.Boolean(), nullable=True, default=False),
        sa.Column("error_response_code", sa.Integer(), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=True, default=0),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create an index on weather_date_fetched for efficient queries
    op.create_index(
        "idx_weather_date_fetched", "weather_data", ["weather_date_fetched"]
    )

    # Migrate existing weather data from settings table if it exists
    op.execute(
        """
        INSERT INTO weather_data (
            weather_date_fetched,
            current_temp,
            current_weather_icon,
            current_weather_description,
            sunrise_timestamp,
            sunset_timestamp,
            created_at
        )
        SELECT
            CASE
                WHEN s1.value != '' THEN s1.value::timestamp with time zone
                ELSE NULL
            END as weather_date_fetched,
            CASE
                WHEN s2.value != '' THEN s2.value::float
                ELSE NULL
            END as current_temp,
            CASE
                WHEN s3.value != '' THEN s3.value
                ELSE NULL
            END as current_weather_icon,
            CASE
                WHEN s4.value != '' THEN s4.value
                ELSE NULL
            END as current_weather_description,
            CASE
                WHEN s5.value != '' THEN s5.value::timestamp with time zone
                ELSE NULL
            END as sunrise_timestamp,
            CASE
                WHEN s6.value != '' THEN s6.value::timestamp with time zone
                ELSE NULL
            END as sunset_timestamp,
            CURRENT_TIMESTAMP as created_at
        FROM
            (SELECT value FROM settings WHERE key = 'weather_date_fetched') s1,
            (SELECT value FROM settings WHERE key = 'current_temp') s2,
            (SELECT value FROM settings WHERE key = 'current_weather_icon') s3,
            (SELECT value FROM settings WHERE key = 'current_weather_description') s4,
            (SELECT value FROM settings WHERE key = 'sunrise_timestamp') s5,
            (SELECT value FROM settings WHERE key = 'sunset_timestamp') s6
        WHERE
            EXISTS (SELECT 1 FROM settings WHERE key = 'weather_date_fetched' AND value != '')
    """
    )

    # Remove weather data fields from settings table (keep configuration fields)
    op.execute(
        """
        DELETE FROM settings WHERE key IN (
            'current_temp',
            'current_weather_icon',
            'current_weather_description',
            'weather_date_fetched',
            'sunrise_timestamp',
            'sunset_timestamp'
        )
    """
    )


def downgrade() -> None:
    """Move weather data back to settings and drop weather table"""

    result = (
        op.get_bind()
        .execute(text("SELECT * FROM weather_data ORDER BY created_at DESC LIMIT 1"))
        .fetchone()
    )

    if result:
        # Re-insert weather data into settings table
        weather_data = dict(result)
        settings_data = [
            ("weather_date_fetched", str(weather_data.get("weather_date_fetched", ""))),
            ("current_temp", str(weather_data.get("current_temp", ""))),
            ("current_weather_icon", weather_data.get("current_weather_icon", "")),
            (
                "current_weather_description",
                weather_data.get("current_weather_description", ""),
            ),
            ("sunrise_timestamp", str(weather_data.get("sunrise_timestamp", ""))),
            ("sunset_timestamp", str(weather_data.get("sunset_timestamp", ""))),
        ]

        for key, value in settings_data:
            op.execute(
                f"INSERT INTO settings (key, value) VALUES ('{key}', '{value}') "
                f"ON CONFLICT (key) DO UPDATE SET value = '{value}'"
            )

    # Drop the weather data table
    op.drop_index("idx_weather_date_fetched", table_name="weather_data")
    op.drop_table("weather_data")
