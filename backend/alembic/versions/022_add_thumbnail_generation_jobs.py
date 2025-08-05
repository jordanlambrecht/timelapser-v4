"""Add thumbnail generation jobs table

Revision ID: 022_thumbnail_jobs
Revises: 44e164e68feb
Create Date: 2025-01-07 12:00:00.000000

"""

# Import enums for default values
import sys
from pathlib import Path

import sqlalchemy as sa

from alembic import op
from app.enums import JobPriority, JobStatus, ThumbnailJobType

sys.path.append(str(Path(__file__).parent.parent.parent / "app"))


# revision identifiers, used by Alembic.
revision = "022_thumbnail_jobs"
down_revision = "44e164e68feb"
branch_labels = None
depends_on = None


def upgrade():
    """Create thumbnail_generation_jobs table for background thumbnail processing."""

    # Create the thumbnail_generation_jobs table
    op.create_table(
        "thumbnail_generation_jobs",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("image_id", sa.Integer(), nullable=False),
        sa.Column(
            "priority",
            sa.String(20),
            nullable=False,
            default=JobPriority.MEDIUM,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            default=JobStatus.PENDING,
        ),
        sa.Column(
            "job_type", sa.String(20), nullable=False, default=ThumbnailJobType.SINGLE
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, default=0),
        # Foreign key constraint to images table
        sa.ForeignKeyConstraint(["image_id"], ["images.id"], ondelete="CASCADE"),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for efficient querying
    op.create_index(
        "idx_thumbnail_jobs_status_priority",
        "thumbnail_generation_jobs",
        ["status", "priority", "created_at"],
    )

    op.create_index(
        "idx_thumbnail_jobs_image_id", "thumbnail_generation_jobs", ["image_id"]
    )

    op.create_index(
        "idx_thumbnail_jobs_created_at", "thumbnail_generation_jobs", ["created_at"]
    )

    # Create index for cleanup operations (completed jobs older than X hours)
    op.create_index(
        "idx_thumbnail_jobs_cleanup",
        "thumbnail_generation_jobs",
        ["status", "completed_at"],
    )


def downgrade():
    """Drop thumbnail_generation_jobs table and related indexes."""

    # Drop indexes first
    op.drop_index("idx_thumbnail_jobs_cleanup", table_name="thumbnail_generation_jobs")
    op.drop_index(
        "idx_thumbnail_jobs_created_at", table_name="thumbnail_generation_jobs"
    )
    op.drop_index("idx_thumbnail_jobs_image_id", table_name="thumbnail_generation_jobs")
    op.drop_index(
        "idx_thumbnail_jobs_status_priority", table_name="thumbnail_generation_jobs"
    )

    # Drop the table
    op.drop_table("thumbnail_generation_jobs")
