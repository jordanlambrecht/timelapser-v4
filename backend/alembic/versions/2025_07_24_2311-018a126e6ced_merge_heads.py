"""merge heads

Revision ID: 018a126e6ced
Revises: 029_capture_intervals, 39831704dd35
Create Date: 2025-07-24 23:11:59.322728

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "018a126e6ced"
down_revision: tuple[str, ...] | None = ("029_capture_intervals", "39831704dd35")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
