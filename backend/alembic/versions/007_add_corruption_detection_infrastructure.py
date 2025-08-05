"""Add corruption detection infrastructure

Revision ID: 007_corruption_detection
Revises: 006_enhanced_settings
Create Date: 2025-06-20 15:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers
revision = "007_corruption_detection"
down_revision = "006_enhanced_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add corruption detection infrastructure"""

    # Create corruption_logs table
    op.create_table(
        "corruption_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.Integer(), nullable=True),
        sa.Column("corruption_score", sa.Integer(), nullable=False),
        sa.Column("fast_score", sa.Integer(), nullable=True),
        sa.Column("heavy_score", sa.Integer(), nullable=True),
        sa.Column(
            "detection_details", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("action_taken", sa.String(length=50), nullable=False),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "corruption_score >= 0 AND corruption_score <= 100",
            name="corruption_logs_corruption_score_check",
        ),
        sa.CheckConstraint(
            "fast_score IS NULL OR (fast_score >= 0 AND fast_score <= 100)",
            name="corruption_logs_fast_score_check",
        ),
        sa.CheckConstraint(
            "heavy_score IS NULL OR (heavy_score >= 0 AND heavy_score <= 100)",
            name="corruption_logs_heavy_score_check",
        ),
        sa.ForeignKeyConstraint(["camera_id"], ["cameras.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["image_id"], ["images.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes on corruption_logs
    op.create_index("idx_corruption_logs_camera_id", "corruption_logs", ["camera_id"])
    op.create_index("idx_corruption_logs_created_at", "corruption_logs", ["created_at"])
    op.create_index(
        "idx_corruption_logs_score", "corruption_logs", ["corruption_score"]
    )

    # Add corruption detection fields to cameras table
    op.add_column(
        "cameras",
        sa.Column(
            "lifetime_glitch_count", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "cameras",
        sa.Column(
            "consecutive_corruption_failures",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "cameras",
        sa.Column(
            "corruption_detection_heavy",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "cameras",
        sa.Column("last_degraded_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "cameras",
        sa.Column(
            "degraded_mode_active", sa.Boolean(), nullable=False, server_default="false"
        ),
    )

    # Add corruption detection fields to images table
    op.add_column(
        "images",
        sa.Column(
            "corruption_score", sa.Integer(), nullable=False, server_default="100"
        ),
    )
    op.add_column(
        "images",
        sa.Column("is_flagged", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "images",
        sa.Column(
            "corruption_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )

    # Add check constraint for corruption_score
    op.create_check_constraint(
        "images_corruption_score_check",
        "images",
        "corruption_score >= 0 AND corruption_score <= 100",
    )

    # Add corruption detection fields to timelapses table
    op.add_column(
        "timelapses",
        sa.Column("glitch_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "timelapses",
        sa.Column(
            "total_corruption_score",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )

    # Add corruption detection settings to settings table
    op.execute(
        """
        INSERT INTO settings (key, value) VALUES
        ('corruption_detection_enabled', 'true'),
        ('corruption_score_threshold', '70'),
        ('corruption_auto_discard_enabled', 'false'),
        ('corruption_auto_disable_degraded', 'false'),
        ('corruption_degraded_consecutive_threshold', '10'),
        ('corruption_degraded_time_window_minutes', '30'),
        ('corruption_degraded_failure_percentage', '50')
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    """Remove corruption detection infrastructure"""

    # Remove corruption detection settings
    op.execute(
        """
        DELETE FROM settings WHERE key IN (
            'corruption_detection_enabled',
            'corruption_score_threshold',
            'corruption_auto_discard_enabled',
            'corruption_auto_disable_degraded',
            'corruption_degraded_consecutive_threshold',
            'corruption_degraded_time_window_minutes',
            'corruption_degraded_failure_percentage'
        )
        """
    )

    # Remove columns from timelapses table
    op.drop_column("timelapses", "total_corruption_score")
    op.drop_column("timelapses", "glitch_count")

    # Remove columns from images table
    op.drop_constraint("images_corruption_score_check", "images")
    op.drop_column("images", "corruption_details")
    op.drop_column("images", "is_flagged")
    op.drop_column("images", "corruption_score")

    # Remove columns from cameras table
    op.drop_column("cameras", "degraded_mode_active")
    op.drop_column("cameras", "last_degraded_at")
    op.drop_column("cameras", "corruption_detection_heavy")
    op.drop_column("cameras", "consecutive_corruption_failures")
    op.drop_column("cameras", "lifetime_glitch_count")

    # Drop corruption_logs table and indexes
    op.drop_index("idx_corruption_logs_score", table_name="corruption_logs")
    op.drop_index("idx_corruption_logs_created_at", table_name="corruption_logs")
    op.drop_index("idx_corruption_logs_camera_id", table_name="corruption_logs")
    op.drop_table("corruption_logs")
