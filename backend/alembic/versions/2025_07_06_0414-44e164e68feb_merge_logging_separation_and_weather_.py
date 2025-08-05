"""Merge logging separation and weather table changes

Revision ID: 44e164e68feb
Revises: 021_separate_logging_systems, 020_weather_single_row_table
Create Date: 2025-07-06 04:14:44.282661

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "44e164e68feb"
down_revision: tuple[str, ...] = (
    "021_separate_logging_systems",
    "020_weather_single_row_table",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
