"""Add last_image_id and next_capture_at to cameras table

Revision ID: 001_add_camera_image_relations
Revises:
Create Date: 2025-01-13 10:30:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "001_add_camera_image_relations"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add last_image_id and next_capture_at columns to cameras table"""

    # Add the new columns
    op.add_column("cameras", sa.Column("last_image_id", sa.Integer(), nullable=True))
    op.add_column(
        "cameras", sa.Column("next_capture_at", sa.TIMESTAMP(), nullable=True)
    )

    # Add foreign key constraint for last_image_id
    op.create_foreign_key(
        "fk_cameras_last_image_id",
        "cameras",
        "images",
        ["last_image_id"],
        ["id"],
        ondelete="SET NULL",  # If image is deleted, set camera's last_image_id to NULL
    )

    # Create index for performance
    op.create_index("idx_cameras_last_image_id", "cameras", ["last_image_id"])
    op.create_index("idx_cameras_next_capture_at", "cameras", ["next_capture_at"])


def downgrade() -> None:
    """Remove last_image_id and next_capture_at columns from cameras table"""

    # Drop indexes
    op.drop_index("idx_cameras_next_capture_at", table_name="cameras")
    op.drop_index("idx_cameras_last_image_id", table_name="cameras")

    # Drop foreign key constraint
    op.drop_constraint("fk_cameras_last_image_id", "cameras", type_="foreignkey")

    # Drop columns
    op.drop_column("cameras", "next_capture_at")
    op.drop_column("cameras", "last_image_id")
