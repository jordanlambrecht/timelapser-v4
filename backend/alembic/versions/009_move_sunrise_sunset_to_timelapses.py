"""Move sunrise/sunset settings to per-timelapse configuration

Revision ID: 009
Revises: 008
Create Date: 2025-06-21 12:30:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "009"
down_revision = "008_add_weather_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new fields to timelapses table
    op.add_column(
        "timelapses",
        sa.Column(
            "time_window_type", sa.String(20), nullable=False, server_default="none"
        ),
    )
    op.add_column(
        "timelapses", sa.Column("sunrise_offset_minutes", sa.Integer(), nullable=True)
    )
    op.add_column(
        "timelapses", sa.Column("sunset_offset_minutes", sa.Integer(), nullable=True)
    )

    # Add check constraint for time_window_type
    op.create_check_constraint(
        "ck_timelapses_time_window_type",
        "timelapses",
        "time_window_type IN ('none', 'time', 'sunrise_sunset')",
    )

    # Remove sunrise/sunset settings from key-value settings table (not columns!)
    op.execute(
        "DELETE FROM settings WHERE key IN ('sunrise_offset_minutes', 'sunset_offset_minutes')"
    )


def downgrade() -> None:
    # Add sunrise/sunset settings back to key-value settings table
    op.execute(
        "INSERT INTO settings (key, value) VALUES ('sunrise_offset_minutes', '0'), ('sunset_offset_minutes', '0')"
    )

    # Remove fields from timelapses table
    op.drop_constraint("ck_timelapses_time_window_type", "timelapses")
    op.drop_column("timelapses", "sunset_offset_minutes")
    op.drop_column("timelapses", "sunrise_offset_minutes")
    op.drop_column("timelapses", "time_window_type")
