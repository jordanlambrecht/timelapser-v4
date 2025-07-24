"""merge_crop_settings_and_rotation_branches

Revision ID: ee4dc446f0cd
Revises: 029_add_camera_rotation, 033_add_weather_to_images
Create Date: 2025-07-11 00:19:07.331571

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee4dc446f0cd'
down_revision: Union[str, None] = ('029_add_camera_rotation', '033_add_weather_to_images')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
