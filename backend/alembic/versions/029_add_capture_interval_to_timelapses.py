"""Add capture_interval_seconds to timelapses table

Revision ID: 029_capture_intervals
Revises: 028_thumbnail_counts
Create Date: 2025-07-11 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "029_capture_intervals"
down_revision = "028_thumbnail_counts"
branch_labels = None
depends_on = None


def upgrade():
    """Add capture_interval_seconds column to timelapses table."""

    # Add column with default value (5 minutes = 300 seconds)
    op.add_column(
        "timelapses",
        sa.Column(
            "capture_interval_seconds",
            sa.Integer(),
            nullable=False,
            server_default="300",
        ),
    )

    # Add check constraint for reasonable interval values (30 seconds to 24 hours)
    op.create_check_constraint(
        "ck_timelapses_capture_interval_range",
        "timelapses",
        "capture_interval_seconds >= 30 AND capture_interval_seconds <= 86400",
    )

    # Create index for efficient scheduling queries
    op.create_index(
        "idx_timelapses_scheduling",
        "timelapses",
        ["status", "capture_interval_seconds"],
    )


def downgrade():
    """Remove capture_interval_seconds column."""

    # Drop index first
    op.drop_index("idx_timelapses_scheduling", table_name="timelapses")

    # Drop check constraint
    op.drop_constraint("ck_timelapses_capture_interval_range", "timelapses")

    # Drop column
    op.drop_column("timelapses", "capture_interval_seconds")
