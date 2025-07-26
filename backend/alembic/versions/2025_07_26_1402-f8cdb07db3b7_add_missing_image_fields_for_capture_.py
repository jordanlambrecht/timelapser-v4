"""add_missing_image_fields_for_capture_pipeline

Revision ID: f8cdb07db3b7
Revises: 018a126e6ced
Create Date: 2025-07-26 14:02:55.961197

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8cdb07db3b7'
down_revision: Union[str, None] = '018a126e6ced'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add missing columns required by capture pipeline
    op.add_column('images', sa.Column('corruption_detected', sa.Boolean(), nullable=True))
    op.add_column('images', sa.Column('weather_temperature', sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column('images', sa.Column('weather_conditions', sa.Text(), nullable=True))
    op.add_column('images', sa.Column('weather_icon', sa.String(50), nullable=True))
    op.add_column('images', sa.Column('weather_fetched_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Remove the added columns in reverse order
    op.drop_column('images', 'weather_fetched_at')
    op.drop_column('images', 'weather_icon')
    op.drop_column('images', 'weather_conditions')
    op.drop_column('images', 'weather_temperature')
    op.drop_column('images', 'corruption_detected')
