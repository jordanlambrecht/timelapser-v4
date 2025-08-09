"""add_overlay_columns_to_timelapses

Revision ID: 4749455ef1b9
Revises: 922bd647d7ad
Create Date: 2025-08-08 21:47:32.993809

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4749455ef1b9"
down_revision: Union[str, None] = "922bd647d7ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add overlay_config JSONB column to store overlay configuration
    op.execute(
        "ALTER TABLE timelapses ADD COLUMN overlay_config JSONB DEFAULT '{}' NOT NULL"
    )

    # Add enable_overlays boolean column to control overlay rendering
    op.add_column(
        "timelapses",
        sa.Column(
            "enable_overlays", sa.Boolean(), nullable=False, server_default="false"
        ),
    )

    # Add index for efficient overlay config queries (JSONB supports GIN indexes natively)
    op.execute(
        "CREATE INDEX idx_timelapses_overlay_config_gin ON timelapses USING gin (overlay_config)"
    )

    # Add index for filtering timelapses with overlays enabled
    op.execute(
        "CREATE INDEX idx_timelapses_enable_overlays ON timelapses (enable_overlays) WHERE enable_overlays = true"
    )

    # Add comments for documentation
    op.execute(
        "COMMENT ON COLUMN timelapses.overlay_config IS 'JSONB configuration for overlay rendering on this timelapse'"
    )
    op.execute(
        "COMMENT ON COLUMN timelapses.enable_overlays IS 'Whether overlay rendering is enabled for this timelapse'"
    )


def downgrade() -> None:
    # Drop indexes first
    op.execute("DROP INDEX IF EXISTS idx_timelapses_overlay_config_gin")
    op.execute("DROP INDEX IF EXISTS idx_timelapses_enable_overlays")

    # Drop columns
    op.drop_column("timelapses", "enable_overlays")
    op.drop_column("timelapses", "overlay_config")
