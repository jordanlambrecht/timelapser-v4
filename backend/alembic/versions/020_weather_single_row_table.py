"""Convert weather_data to single-row table

Revision ID: 020_weather_single_row_table
Revises: 019_create_weather_table
Create Date: 2025-01-06 00:00:00.000000

"""

from alembic import op

# revision identifiers
revision = "020_weather_single_row_table"
down_revision = "019_create_weather_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Convert weather_data to single-row table with constraint"""

    # Add a constraint to ensure only one row can exist
    # We'll use a partial unique index on a constant value
    op.execute(
        """
        ALTER TABLE weather_data
        ADD COLUMN IF NOT EXISTS single_row_enforcer INTEGER DEFAULT 1 CHECK (single_row_enforcer = 1)
    """
    )

    # Create a unique constraint on the enforcer column
    op.create_unique_constraint(
        "uq_weather_data_single_row", "weather_data", ["single_row_enforcer"]
    )

    # Since there's no existing data (system not working), we don't need cleanup
    # But let's add a comment for clarity
    op.execute(
        """
        COMMENT ON TABLE weather_data IS 'Single-row table for current weather state. Uses UPSERT pattern to maintain only one row.'
    """
    )

    op.execute(
        """
        COMMENT ON COLUMN weather_data.single_row_enforcer IS 'Ensures only one row can exist in this table'
    """
    )


def downgrade() -> None:
    """Remove single-row constraint from weather_data"""

    # Remove the unique constraint
    op.drop_constraint("uq_weather_data_single_row", "weather_data", type_="unique")

    # Remove the enforcer column
    op.drop_column("weather_data", "single_row_enforcer")

    # Remove table comment
    op.execute(
        """
        COMMENT ON TABLE weather_data IS NULL
    """
    )
