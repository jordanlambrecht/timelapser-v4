"""Fix settings table structure - remove corruption columns

Revision ID: 012_fix_settings_table_structure
Revises: 011_separate_video_modes
Create Date: 2025-06-23 09:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "012_fix_settings_table_structure"
down_revision: Union[str, None] = "011_separate_video_modes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove corruption detection columns from settings table.
    These should be stored as rows (key-value pairs) not columns.
    """

    # First, ensure the corruption settings exist as rows before dropping columns
    # (They should already exist from migration 007, but let's be safe)
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

    # Drop the check constraint first
    op.drop_constraint(
        "settings_corruption_score_threshold_check", "settings", type_="check"
    )

    # Drop all the corruption detection columns from settings table
    op.drop_column("settings", "corruption_degraded_failure_percentage")
    op.drop_column("settings", "corruption_degraded_time_window_minutes")
    op.drop_column("settings", "corruption_degraded_consecutive_threshold")
    op.drop_column("settings", "corruption_auto_disable_degraded")
    op.drop_column("settings", "corruption_auto_discard_enabled")
    op.drop_column("settings", "corruption_score_threshold")
    op.drop_column("settings", "corruption_detection_enabled")


def downgrade() -> None:
    """
    Add back corruption detection columns to settings table.
    (Not recommended - these should be stored as key-value rows)
    """

    # Add corruption detection columns back to settings table
    op.add_column(
        "settings",
        sa.Column("corruption_detection_enabled", sa.Boolean(), server_default="true"),
    )
    op.add_column(
        "settings",
        sa.Column("corruption_score_threshold", sa.Integer(), server_default="70"),
    )
    op.add_column(
        "settings",
        sa.Column(
            "corruption_auto_discard_enabled", sa.Boolean(), server_default="false"
        ),
    )
    op.add_column(
        "settings",
        sa.Column(
            "corruption_auto_disable_degraded", sa.Boolean(), server_default="false"
        ),
    )
    op.add_column(
        "settings",
        sa.Column(
            "corruption_degraded_consecutive_threshold",
            sa.Integer(),
            server_default="10",
        ),
    )
    op.add_column(
        "settings",
        sa.Column(
            "corruption_degraded_time_window_minutes", sa.Integer(), server_default="30"
        ),
    )
    op.add_column(
        "settings",
        sa.Column(
            "corruption_degraded_failure_percentage", sa.Integer(), server_default="50"
        ),
    )

    # Add back the check constraint
    op.create_check_constraint(
        "settings_corruption_score_threshold_check",
        "settings",
        "corruption_score_threshold >= 0 AND corruption_score_threshold <= 100",
    )
