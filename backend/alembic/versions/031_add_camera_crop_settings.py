"""Add camera crop and aspect ratio settings

Revision ID: 031_add_camera_crop_settings
Revises: 1d191b084f88
Create Date: 2025-01-23 01:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "031_add_camera_crop_settings"
down_revision: Union[str, None] = "1d191b084f88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add crop and aspect ratio settings to cameras table"""
    
    # Check if crop_rotation_settings column already exists
    connection = op.get_bind()
    result = connection.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'cameras' 
        AND column_name = 'crop_rotation_settings'
    """))
    
    if not result.fetchone():
        # Add crop_rotation_settings JSONB column
        op.add_column(
            "cameras",
            sa.Column(
                "crop_rotation_settings",
                postgresql.JSONB(),
                nullable=True,
                server_default="{}",
                comment="Camera crop, rotation, and aspect ratio settings"
            ),
        )
        
        print("Added crop_rotation_settings column to cameras table")
    else:
        print("crop_rotation_settings column already exists")
    
    # Check if crop_rotation_enabled column already exists
    result = connection.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'cameras' 
        AND column_name = 'crop_rotation_enabled'
    """))
    
    if not result.fetchone():
        # Add crop_rotation_enabled boolean column
        op.add_column(
            "cameras",
            sa.Column(
                "crop_rotation_enabled",
                sa.Boolean(),
                nullable=False,
                server_default="false",
                comment="Whether camera has custom crop/rotation settings enabled"
            ),
        )
        
        print("Added crop_rotation_enabled column to cameras table")
    else:
        print("crop_rotation_enabled column already exists")
    
    # Check if source_resolution column already exists
    result = connection.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'cameras' 
        AND column_name = 'source_resolution'
    """))
    
    if not result.fetchone():
        # Add source_resolution JSONB column
        op.add_column(
            "cameras",
            sa.Column(
                "source_resolution",
                postgresql.JSONB(),
                nullable=True,
                server_default="{}",
                comment="Original camera resolution (width, height) before any processing"
            ),
        )
        
        print("Added source_resolution column to cameras table")
    else:
        print("source_resolution column already exists")
    
    # Create performance index for crop_rotation_settings
    try:
        op.create_index(
            "idx_cameras_crop_rotation_settings",
            "cameras",
            ["crop_rotation_settings"],
            postgresql_using="gin",
            if_not_exists=True
        )
        print("Created GIN index on crop_rotation_settings")
    except Exception as e:
        print(f"Index creation skipped (may already exist): {e}")


def downgrade() -> None:
    """Remove crop and aspect ratio settings from cameras table"""
    
    # Drop index
    try:
        op.drop_index("idx_cameras_crop_rotation_settings", table_name="cameras")
    except Exception:
        pass  # Index may not exist
    
    # Drop columns
    op.drop_column("cameras", "source_resolution")
    op.drop_column("cameras", "crop_rotation_enabled")
    op.drop_column("cameras", "crop_rotation_settings")
