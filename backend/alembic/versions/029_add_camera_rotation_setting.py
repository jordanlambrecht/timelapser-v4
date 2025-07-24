"""Add rotation setting to cameras table

Revision ID: 029_add_camera_rotation
Revises: 028_add_thumbnail_counts_to_timelapses
Create Date: 2025-01-23 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "029_add_camera_rotation"
down_revision: Union[str, None] = "028_thumbnail_counts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add rotation field to cameras table for image capture orientation"""

    # Check if rotation column already exists
    connection = op.get_bind()
    result = connection.execute(
        sa.text(
            """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'cameras' 
        AND column_name = 'rotation'
    """
        )
    )

    if not result.fetchone():
        # Column doesn't exist, add it
        op.add_column(
            "cameras",
            sa.Column(
                "rotation",
                sa.Integer(),
                nullable=False,
                server_default="0",
                comment="Camera rotation in degrees (0, 90, 180, 270)",
            ),
        )

        # Add check constraint to ensure only valid rotation values
        op.create_check_constraint(
            "ck_cameras_rotation_valid",
            "cameras",
            "rotation IN (0, 90, 180, 270)",
        )

        print("Added rotation column to cameras table with default value 0")
    else:
        print("Rotation column already exists in cameras table")


def downgrade() -> None:
    """Remove rotation field from cameras table"""

    # Drop check constraint
    op.drop_constraint("ck_cameras_rotation_valid", "cameras", type_="check")

    # Drop column
    op.drop_column("cameras", "rotation")
