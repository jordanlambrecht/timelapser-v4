"""Add scheduled_jobs table for scheduling visibility and persistence

Revision ID: 040_add_scheduled_jobs_table
Revises: 039
Create Date: 2025-07-26 12:00:00.000000

This migration adds a scheduled_jobs table to provide visibility into APScheduler
jobs and enable persistence across restarts. This supports the hybrid scheduling
approach where APScheduler remains the execution engine but the database provides
visibility, audit trails, and recovery capabilities.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "040_add_scheduled_jobs_table"
down_revision: Union[str, None] = "f8cdb07db3b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add scheduled_jobs table for scheduling visibility and persistence."""

    # Create scheduled_jobs table
    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.VARCHAR(100), nullable=False),
        sa.Column("job_type", sa.VARCHAR(50), nullable=False),
        sa.Column("schedule_pattern", sa.VARCHAR(100), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=True),
        sa.Column("next_run_time", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_run_time", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_success_time", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_failure_time", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("entity_type", sa.VARCHAR(50), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.VARCHAR(20), nullable=False, server_default="active"),
        sa.Column("execution_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", name="uq_scheduled_jobs_job_id"),
    )

    # Create indexes for efficient querying
    op.create_index("idx_scheduled_jobs_status", "scheduled_jobs", ["status"])

    op.create_index("idx_scheduled_jobs_job_type", "scheduled_jobs", ["job_type"])

    op.create_index(
        "idx_scheduled_jobs_entity", "scheduled_jobs", ["entity_type", "entity_id"]
    )

    op.create_index("idx_scheduled_jobs_next_run", "scheduled_jobs", ["next_run_time"])

    op.create_index("idx_scheduled_jobs_last_run", "scheduled_jobs", ["last_run_time"])

    # Create job execution log table for detailed tracking
    op.create_table(
        "scheduled_job_executions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.VARCHAR(100), nullable=False),
        sa.Column("scheduled_job_id", sa.Integer(), nullable=False),
        sa.Column("execution_start", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("execution_end", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.VARCHAR(20), nullable=False),
        sa.Column("result_message", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("execution_duration_ms", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["scheduled_job_id"], ["scheduled_jobs.id"], ondelete="CASCADE"
        ),
    )

    # Create indexes for job execution log
    op.create_index(
        "idx_scheduled_job_executions_job_id", "scheduled_job_executions", ["job_id"]
    )

    op.create_index(
        "idx_scheduled_job_executions_scheduled_job_id",
        "scheduled_job_executions",
        ["scheduled_job_id"],
    )

    op.create_index(
        "idx_scheduled_job_executions_status", "scheduled_job_executions", ["status"]
    )

    op.create_index(
        "idx_scheduled_job_executions_start_time",
        "scheduled_job_executions",
        ["execution_start"],
    )

    # Add comments for documentation
    op.execute(
        """
        COMMENT ON TABLE scheduled_jobs IS 'Tracks APScheduler jobs for visibility and persistence across restarts';
        COMMENT ON COLUMN scheduled_jobs.job_id IS 'Unique job identifier matching APScheduler job_id';
        COMMENT ON COLUMN scheduled_jobs.job_type IS 'Type of job (timelapse_capture, health_check, video_automation, etc.)';
        COMMENT ON COLUMN scheduled_jobs.schedule_pattern IS 'Cron expression or interval description';
        COMMENT ON COLUMN scheduled_jobs.interval_seconds IS 'Interval in seconds for interval-based jobs';
        COMMENT ON COLUMN scheduled_jobs.entity_id IS 'ID of related entity (camera_id, timelapse_id, etc.)';
        COMMENT ON COLUMN scheduled_jobs.entity_type IS 'Type of related entity (camera, timelapse, system)';
        COMMENT ON COLUMN scheduled_jobs.config IS 'Job-specific configuration and parameters';
        COMMENT ON COLUMN scheduled_jobs.status IS 'Job status: active, paused, disabled, error';
        
        COMMENT ON TABLE scheduled_job_executions IS 'Detailed log of job executions for monitoring and debugging';
        COMMENT ON COLUMN scheduled_job_executions.status IS 'Execution status: running, completed, failed, timeout';
    """
    )


def downgrade() -> None:
    """Remove scheduled_jobs table and related structures."""

    # Drop indexes first
    op.drop_index(
        "idx_scheduled_job_executions_start_time", table_name="scheduled_job_executions"
    )
    op.drop_index(
        "idx_scheduled_job_executions_status", table_name="scheduled_job_executions"
    )
    op.drop_index(
        "idx_scheduled_job_executions_scheduled_job_id",
        table_name="scheduled_job_executions",
    )
    op.drop_index(
        "idx_scheduled_job_executions_job_id", table_name="scheduled_job_executions"
    )

    op.drop_index("idx_scheduled_jobs_last_run", table_name="scheduled_jobs")
    op.drop_index("idx_scheduled_jobs_next_run", table_name="scheduled_jobs")
    op.drop_index("idx_scheduled_jobs_entity", table_name="scheduled_jobs")
    op.drop_index("idx_scheduled_jobs_job_type", table_name="scheduled_jobs")
    op.drop_index("idx_scheduled_jobs_status", table_name="scheduled_jobs")

    # Drop tables
    op.drop_table("scheduled_job_executions")
    op.drop_table("scheduled_jobs")
