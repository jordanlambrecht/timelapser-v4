"""Create settings table

Revision ID: 002_create_settings_table
Revises: 2025_06_14_1532-9c9b5c2bbdbc_remove_redundant_last_image_path
Create Date: 2025-06-16 09:30:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "002_create_settings_table"
down_revision = "9c9b5c2bbdbc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create settings table"""

    # Create settings table
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(255), nullable=False, unique=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # Create unique index on key for fast lookups
    op.create_index("idx_settings_key", "settings", ["key"], unique=True)

    # Insert default settings
    op.execute(
        """
        INSERT INTO settings (key, value) VALUES 
        ('capture_interval', '300'),
        ('timezone', 'America/Chicago')
        """
    )


def downgrade() -> None:
    """Drop settings table"""
    op.drop_index("idx_settings_key", table_name="settings")
    op.drop_table("settings")
