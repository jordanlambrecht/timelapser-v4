"""empty message

Revision ID: 39d14c373e84
Revises: 040_add_scheduled_jobs_table, 20250726_add_is_flagged
Create Date: 2025-07-26 16:57:29.159189

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "39d14c373e84"
down_revision: tuple[str, ...] | None = (
    "040_add_scheduled_jobs_table",
    "20250726_add_is_flagged",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
