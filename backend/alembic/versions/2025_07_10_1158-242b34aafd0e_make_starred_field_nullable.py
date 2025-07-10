"""make_starred_field_nullable

Revision ID: 242b34aafd0e
Revises: 030_remove_migrated_fields
Create Date: 2025-07-10 11:58:39.803990

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '242b34aafd0e'
down_revision: Union[str, None] = '030_remove_migrated_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make starred field nullable to allow true optional behavior"""
    # Change starred field to allow NULL values
    op.alter_column(
        "timelapses",
        "starred",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    """Revert starred field to NOT NULL with default false"""
    # First update any NULL values to false
    op.execute("UPDATE timelapses SET starred = false WHERE starred IS NULL")
    
    # Then make the field NOT NULL again with default false
    op.alter_column(
        "timelapses",
        "starred",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
