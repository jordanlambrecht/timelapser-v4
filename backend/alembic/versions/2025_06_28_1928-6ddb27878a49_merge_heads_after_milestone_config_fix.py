"""Merge heads after milestone_config fix

Revision ID: 6ddb27878a49
Revises: 013_fix_absolute_paths, 015_add_milestone_config_to_cameras
Create Date: 2025-06-28 19:28:55.698118

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision = "6ddb27878a49"
down_revision = ("013_fix_absolute_paths", "015_milestone_config")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
