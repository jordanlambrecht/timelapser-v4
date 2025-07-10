"""Remove migrated fields from cameras table

Revision ID: 030_remove_migrated_fields
Revises: 029_add_starred_field
Create Date: 2025-07-09

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "030_remove_migrated_fields"
down_revision = "029_add_starred_field"
branch_labels = None
depends_on = None


def upgrade():
    """Remove fields that have been migrated to timelapse domain"""

    # Remove time window fields
    op.drop_column("cameras", "time_window_start")
    op.drop_column("cameras", "time_window_end")
    op.drop_column("cameras", "use_time_window")

    # Remove video generation fields
    op.drop_column("cameras", "video_generation_mode")
    op.drop_column("cameras", "standard_fps")
    op.drop_column("cameras", "enable_time_limits")
    op.drop_column("cameras", "min_time_seconds")
    op.drop_column("cameras", "max_time_seconds")
    op.drop_column("cameras", "target_time_seconds")
    op.drop_column("cameras", "fps_bounds_min")
    op.drop_column("cameras", "fps_bounds_max")

    # Remove video automation fields
    op.drop_column("cameras", "video_automation_mode")
    op.drop_column("cameras", "generation_schedule")
    op.drop_column("cameras", "milestone_config")

    print("✅ Removed migrated camera fields")
    print(
        "📦 Time window, video generation, and automation settings now managed by timelapse domain"
    )


def downgrade():
    """Restore migrated fields to cameras table (not recommended)"""

    # Restore time window fields
    op.add_column("cameras", sa.Column("time_window_start", sa.Time(), nullable=True))
    op.add_column("cameras", sa.Column("time_window_end", sa.Time(), nullable=True))
    op.add_column(
        "cameras",
        sa.Column(
            "use_time_window",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Restore video generation fields
    op.add_column(
        "cameras",
        sa.Column(
            "video_generation_mode",
            sa.String(),
            nullable=False,
            server_default="standard",
        ),
    )
    op.add_column(
        "cameras",
        sa.Column("standard_fps", sa.Integer(), nullable=False, server_default="24"),
    )
    op.add_column(
        "cameras",
        sa.Column(
            "enable_time_limits",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("cameras", sa.Column("min_time_seconds", sa.Integer(), nullable=True))
    op.add_column("cameras", sa.Column("max_time_seconds", sa.Integer(), nullable=True))
    op.add_column(
        "cameras", sa.Column("target_time_seconds", sa.Integer(), nullable=True)
    )
    op.add_column(
        "cameras",
        sa.Column("fps_bounds_min", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "cameras",
        sa.Column("fps_bounds_max", sa.Integer(), nullable=False, server_default="60"),
    )

    # Restore video automation fields
    op.add_column(
        "cameras",
        sa.Column(
            "video_automation_mode",
            sa.String(),
            nullable=False,
            server_default="manual",
        ),
    )
    op.add_column("cameras", sa.Column("generation_schedule", sa.JSON(), nullable=True))
    op.add_column("cameras", sa.Column("milestone_config", sa.JSON(), nullable=True))

    print("⚠️  Restored migrated fields to cameras table (not recommended)")
    print("💡 Consider using timelapse-specific settings instead")
