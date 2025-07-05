"""Separate video generation modes - rename automation field

Revision ID: 011_separate_video_modes
Revises: 010_add_video_automation
Create Date: 2025-01-18 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "011_separate_video_modes"
down_revision: Union[str, None] = "010_add_video_automation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Rename video_generation_mode to video_automation_mode to separate concerns:
    - video_generation_mode: for FPS calculation ('standard', 'target')
    - video_automation_mode: for automation behavior ('manual', 'per_capture', 'scheduled', 'milestone')
    """

    # Rename the automation field in cameras table
    op.alter_column(
        "cameras", "video_generation_mode", new_column_name="video_automation_mode"
    )

    # Rename the automation field in timelapses table
    op.alter_column(
        "timelapses", "video_generation_mode", new_column_name="video_automation_mode"
    )

    # Now add the new video_generation_mode field for FPS calculation
    op.add_column(
        "cameras",
        sa.Column(
            "video_generation_mode",
            sa.VARCHAR(20),
            nullable=False,
            server_default="standard",
        ),
    )

    op.add_column(
        "timelapses",
        sa.Column("video_generation_mode", sa.VARCHAR(20), nullable=True),
    )


def downgrade() -> None:
    """
    Reverse the separation - merge back to single field
    """

    # Remove the new FPS calculation fields
    op.drop_column("timelapses", "video_generation_mode")
    op.drop_column("cameras", "video_generation_mode")

    # Rename automation fields back to original name
    op.alter_column(
        "timelapses", "video_automation_mode", new_column_name="video_generation_mode"
    )

    op.alter_column(
        "cameras", "video_automation_mode", new_column_name="video_generation_mode"
    )
