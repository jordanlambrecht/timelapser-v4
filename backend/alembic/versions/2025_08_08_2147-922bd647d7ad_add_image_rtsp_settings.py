"""add_image_rtsp_settings

Revision ID: 922bd647d7ad
Revises: 041_max_db_logs
Create Date: 2025-08-08 21:47:26.422731

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "922bd647d7ad"
down_revision: Union[str, None] = "041_max_db_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add image_quality setting (JPEG quality 1-100, default 90)
    op.execute(
        """
        INSERT INTO settings (key, value, created_at, updated_at)
        VALUES ('image_quality', '90', NOW(), NOW())
        ON CONFLICT (key) DO NOTHING;
    """
    )

    # Add rtsp_timeout_seconds setting (timeout for RTSP connections, default 10)
    op.execute(
        """
        INSERT INTO settings (key, value, created_at, updated_at)
        VALUES ('rtsp_timeout_seconds', '10', NOW(), NOW())
        ON CONFLICT (key) DO NOTHING;
    """
    )


def downgrade() -> None:
    # Remove the added settings
    op.execute(
        "DELETE FROM settings WHERE key IN ('image_quality', 'rtsp_timeout_seconds')"
    )
