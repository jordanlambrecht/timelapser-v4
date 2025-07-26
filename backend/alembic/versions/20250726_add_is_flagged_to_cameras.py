"""
Add is_flagged column to cameras table
"""

from alembic import op
import sqlalchemy as sa


revision = "20250726_add_is_flagged"
down_revision = "018a126e6ced"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "cameras",
        sa.Column(
            "is_flagged", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )


def downgrade():
    op.drop_column("cameras", "is_flagged")
