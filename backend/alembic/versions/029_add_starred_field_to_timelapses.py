"""Add starred field to timelapses

Revision ID: 029_add_starred_field
Revises: 028_add_thumbnail_counts_to_timelapses
Create Date: 2025-07-08

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "029_add_starred_field"
down_revision = "028_thumbnail_counts"
branch_labels = None
depends_on = None


def upgrade():
    """Add starred field to timelapses table"""
    op.add_column(
        "timelapses",
        sa.Column(
            "starred", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )


def downgrade():
    """Remove starred field from timelapses table"""
    op.drop_column("timelapses", "starred")
