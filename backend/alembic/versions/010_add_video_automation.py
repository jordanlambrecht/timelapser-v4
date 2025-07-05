"""Add video automation infrastructure

Revision ID: 010_add_video_automation
Revises: 009_move_sunrise_sunset_to_timelapses
Create Date: 2025-06-21 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "010_add_video_automation"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add video automation fields to cameras table
    op.add_column(
        "cameras",
        sa.Column(
            "video_generation_mode",
            sa.VARCHAR(20),
            nullable=False,
            server_default="manual",
        ),
    )
    op.add_column(
        "cameras",
        sa.Column(
            "generation_schedule",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "cameras",
        sa.Column(
            "milestone_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )

    # Add video automation fields to timelapses table (inheritance pattern)
    op.add_column(
        "timelapses", sa.Column("video_generation_mode", sa.VARCHAR(20), nullable=True)
    )
    op.add_column(
        "timelapses",
        sa.Column(
            "generation_schedule",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "timelapses",
        sa.Column(
            "milestone_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )

    # Create video generation job queue table
    op.create_table(
        "video_generation_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("timelapse_id", sa.Integer(), nullable=False),
        sa.Column("trigger_type", sa.VARCHAR(20), nullable=False),
        sa.Column("status", sa.VARCHAR(20), nullable=False, server_default="pending"),
        sa.Column("priority", sa.VARCHAR(10), nullable=False, server_default="medium"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("video_path", sa.VARCHAR(500), nullable=True),
        sa.Column("video_id", sa.Integer(), nullable=True),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["timelapse_id"], ["timelapses.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="SET NULL"),
    )

    # Create indexes for efficient queue processing
    op.create_index(
        "idx_video_jobs_status_created",
        "video_generation_jobs",
        ["status", "created_at"],
    )
    op.create_index(
        "idx_video_jobs_timelapse_id", "video_generation_jobs", ["timelapse_id"]
    )
    op.create_index(
        "idx_video_jobs_trigger_type", "video_generation_jobs", ["trigger_type"]
    )

    # Add automation tracking fields to videos table
    op.add_column("videos", sa.Column("trigger_type", sa.VARCHAR(20), nullable=True))
    op.add_column("videos", sa.Column("job_id", sa.Integer(), nullable=True))

    # Add foreign key constraint for job_id
    op.create_foreign_key(
        "fk_videos_job_id",
        "videos",
        "video_generation_jobs",
        ["job_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Remove foreign key constraint
    op.drop_constraint("fk_videos_job_id", "videos", type_="foreignkey")

    # Remove columns from videos table
    op.drop_column("videos", "job_id")
    op.drop_column("videos", "trigger_type")

    # Drop indexes
    op.drop_index("idx_video_jobs_trigger_type", table_name="video_generation_jobs")
    op.drop_index("idx_video_jobs_timelapse_id", table_name="video_generation_jobs")
    op.drop_index("idx_video_jobs_status_created", table_name="video_generation_jobs")

    # Drop video generation jobs table
    op.drop_table("video_generation_jobs")

    # Remove automation fields from timelapses table
    op.drop_column("timelapses", "milestone_config")
    op.drop_column("timelapses", "generation_schedule")
    op.drop_column("timelapses", "video_generation_mode")

    # Remove automation fields from cameras table
    op.drop_column("cameras", "milestone_config")
    op.drop_column("cameras", "generation_schedule")
    op.drop_column("cameras", "video_generation_mode")
