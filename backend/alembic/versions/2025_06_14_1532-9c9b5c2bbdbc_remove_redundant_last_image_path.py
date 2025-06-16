"""remove_redundant_last_image_path

Revision ID: 9c9b5c2bbdbc
Revises: 001_add_camera_image_relations
Create Date: 2025-06-14 15:32:26.693941

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c9b5c2bbdbc"
down_revision: Union[str, None] = "001_add_camera_image_relations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove the redundant last_image_path column since we now use last_image_id
    # with proper relational queries
    op.drop_column("cameras", "last_image_path")


def downgrade() -> None:
    # Add back the last_image_path column if needed to rollback
    op.add_column("cameras", sa.Column("last_image_path", sa.Text, nullable=True))
