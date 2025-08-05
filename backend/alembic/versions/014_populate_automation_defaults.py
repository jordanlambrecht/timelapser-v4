"""Populate missing video automation defaults for existing cameras

Revision ID: 014_populate_defaults
Revises: 013_fix_video_automation_mode_data
Create Date: 2025-06-26 12:00:00.000000

"""

from typing import Sequence, Union


from alembic import op

# revision identifiers, used by Alembic.
revision: str = "014_populate_defaults"
down_revision: Union[str, None] = "013a_add_missing_camera_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Ensure all cameras have proper default values for video automation settings.
    This migration addresses any missing defaults that weren't properly set during schema evolution.
    """

    # Update cameras table - ensure all required fields have proper defaults
    op.execute(
        """
        UPDATE cameras 
        SET 
            video_generation_mode = COALESCE(video_generation_mode, 'standard'),
            standard_fps = COALESCE(standard_fps, 12),
            enable_time_limits = COALESCE(enable_time_limits, false),
            fps_bounds_min = COALESCE(fps_bounds_min, 1),
            fps_bounds_max = COALESCE(fps_bounds_max, 60),
            video_automation_mode = COALESCE(video_automation_mode, 'manual'),
            corruption_detection_heavy = COALESCE(corruption_detection_heavy, false),
            corruption_score = COALESCE(corruption_score, 100),
            lifetime_glitch_count = COALESCE(lifetime_glitch_count, 0),
            consecutive_corruption_failures = COALESCE(consecutive_corruption_failures, 0),
            use_time_window = COALESCE(use_time_window, false)
        WHERE 
            video_generation_mode IS NULL 
            OR standard_fps IS NULL 
            OR enable_time_limits IS NULL
            OR fps_bounds_min IS NULL
            OR fps_bounds_max IS NULL
            OR video_automation_mode IS NULL
            OR corruption_detection_heavy IS NULL
            OR corruption_score IS NULL
            OR lifetime_glitch_count IS NULL
            OR consecutive_corruption_failures IS NULL
            OR use_time_window IS NULL
    """
    )

    # Ensure cameras have proper NOT NULL constraints for critical fields
    op.alter_column(
        "cameras", "video_generation_mode", nullable=False, server_default="standard"
    )
    op.alter_column("cameras", "standard_fps", nullable=False, server_default="12")
    op.alter_column(
        "cameras", "enable_time_limits", nullable=False, server_default="false"
    )
    op.alter_column("cameras", "fps_bounds_min", nullable=False, server_default="1")
    op.alter_column("cameras", "fps_bounds_max", nullable=False, server_default="60")
    op.alter_column(
        "cameras", "video_automation_mode", nullable=False, server_default="manual"
    )
    op.alter_column(
        "cameras", "corruption_detection_heavy", nullable=False, server_default="false"
    )
    op.alter_column("cameras", "corruption_score", nullable=False, server_default="100")
    op.alter_column(
        "cameras", "lifetime_glitch_count", nullable=False, server_default="0"
    )
    op.alter_column(
        "cameras", "consecutive_corruption_failures", nullable=False, server_default="0"
    )
    op.alter_column(
        "cameras", "use_time_window", nullable=False, server_default="false"
    )


def downgrade() -> None:
    """
    This migration only populates missing defaults, so downgrade just removes constraints.
    We don't remove the data as it represents proper default values.
    """

    # Remove NOT NULL constraints if needed (allowing NULL again)
    op.alter_column(
        "cameras", "video_generation_mode", nullable=True, server_default=None
    )
    op.alter_column("cameras", "standard_fps", nullable=True, server_default=None)
    op.alter_column("cameras", "enable_time_limits", nullable=True, server_default=None)
    op.alter_column("cameras", "fps_bounds_min", nullable=True, server_default=None)
    op.alter_column("cameras", "fps_bounds_max", nullable=True, server_default=None)
    op.alter_column(
        "cameras", "video_automation_mode", nullable=True, server_default=None
    )
    op.alter_column(
        "cameras", "corruption_detection_heavy", nullable=True, server_default=None
    )
    op.alter_column("cameras", "corruption_score", nullable=True, server_default=None)
    op.alter_column("cameras", "is_flagged", nullable=True, server_default=None)
    op.alter_column(
        "cameras", "lifetime_glitch_count", nullable=True, server_default=None
    )
    op.alter_column(
        "cameras", "consecutive_corruption_failures", nullable=True, server_default=None
    )
    op.alter_column("cameras", "use_time_window", nullable=True, server_default=None)
