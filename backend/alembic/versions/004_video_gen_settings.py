"""Add video generation settings

Revision ID: 004_video_gen_settings
Revises: 003_add_auto_stop_at
Create Date: 2025-06-17 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '004_video_gen_settings'
down_revision = '003_add_auto_stop_at'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create ENUM type for video generation mode
    video_generation_mode_enum = postgresql.ENUM('standard', 'target', name='video_generation_mode')
    video_generation_mode_enum.create(op.get_bind())

    # Add video generation settings to cameras table (nullable first)
    op.add_column('cameras', sa.Column('video_generation_mode', video_generation_mode_enum, nullable=True))
    op.add_column('cameras', sa.Column('standard_fps', sa.Integer(), nullable=True))
    op.add_column('cameras', sa.Column('enable_time_limits', sa.Boolean(), nullable=True))
    op.add_column('cameras', sa.Column('min_time_seconds', sa.Integer(), nullable=True))
    op.add_column('cameras', sa.Column('max_time_seconds', sa.Integer(), nullable=True))
    op.add_column('cameras', sa.Column('target_time_seconds', sa.Integer(), nullable=True))
    op.add_column('cameras', sa.Column('fps_bounds_min', sa.Integer(), nullable=True))
    op.add_column('cameras', sa.Column('fps_bounds_max', sa.Integer(), nullable=True))

    # Set defaults for existing cameras
    op.execute("""
        UPDATE cameras SET 
            video_generation_mode = 'standard',
            standard_fps = 12,
            enable_time_limits = false,
            fps_bounds_min = 1,
            fps_bounds_max = 60
        WHERE video_generation_mode IS NULL
    """)

    # Now make required fields NOT NULL
    op.alter_column('cameras', 'video_generation_mode', nullable=False)
    op.alter_column('cameras', 'standard_fps', nullable=False)
    op.alter_column('cameras', 'enable_time_limits', nullable=False)
    op.alter_column('cameras', 'fps_bounds_min', nullable=False)
    op.alter_column('cameras', 'fps_bounds_max', nullable=False)

    # Add same settings to timelapses table for inheritance/override (all nullable)
    op.add_column('timelapses', sa.Column('video_generation_mode', video_generation_mode_enum, nullable=True))
    op.add_column('timelapses', sa.Column('standard_fps', sa.Integer(), nullable=True))
    op.add_column('timelapses', sa.Column('enable_time_limits', sa.Boolean(), nullable=True))
    op.add_column('timelapses', sa.Column('min_time_seconds', sa.Integer(), nullable=True))
    op.add_column('timelapses', sa.Column('max_time_seconds', sa.Integer(), nullable=True))
    op.add_column('timelapses', sa.Column('target_time_seconds', sa.Integer(), nullable=True))
    op.add_column('timelapses', sa.Column('fps_bounds_min', sa.Integer(), nullable=True))
    op.add_column('timelapses', sa.Column('fps_bounds_max', sa.Integer(), nullable=True))

    # Add calculation metadata to videos table
    op.add_column('videos', sa.Column('calculated_fps', sa.Numeric(precision=6, scale=2), nullable=True))
    op.add_column('videos', sa.Column('target_duration', sa.Integer(), nullable=True))
    op.add_column('videos', sa.Column('actual_duration', sa.Numeric(precision=8, scale=2), nullable=True))
    op.add_column('videos', sa.Column('fps_was_adjusted', sa.Boolean(), default=False, nullable=True))
    op.add_column('videos', sa.Column('adjustment_reason', sa.Text(), nullable=True))

    # Set default for fps_was_adjusted on existing videos
    op.execute("UPDATE videos SET fps_was_adjusted = false WHERE fps_was_adjusted IS NULL")
    
    # Make fps_was_adjusted NOT NULL
    op.alter_column('videos', 'fps_was_adjusted', nullable=False)

def downgrade() -> None:
    # Remove columns from videos table
    op.drop_column('videos', 'adjustment_reason')
    op.drop_column('videos', 'fps_was_adjusted')
    op.drop_column('videos', 'actual_duration')
    op.drop_column('videos', 'target_duration')
    op.drop_column('videos', 'calculated_fps')

    # Remove columns from timelapses table
    op.drop_column('timelapses', 'fps_bounds_max')
    op.drop_column('timelapses', 'fps_bounds_min')
    op.drop_column('timelapses', 'target_time_seconds')
    op.drop_column('timelapses', 'max_time_seconds')
    op.drop_column('timelapses', 'min_time_seconds')
    op.drop_column('timelapses', 'enable_time_limits')
    op.drop_column('timelapses', 'standard_fps')
    op.drop_column('timelapses', 'video_generation_mode')

    # Remove columns from cameras table
    op.drop_column('cameras', 'fps_bounds_max')
    op.drop_column('cameras', 'fps_bounds_min')
    op.drop_column('cameras', 'target_time_seconds')
    op.drop_column('cameras', 'max_time_seconds')
    op.drop_column('cameras', 'min_time_seconds')
    op.drop_column('cameras', 'enable_time_limits')
    op.drop_column('cameras', 'standard_fps')
    op.drop_column('cameras', 'video_generation_mode')

    # Drop ENUM type
    video_generation_mode_enum = postgresql.ENUM('standard', 'target', name='video_generation_mode')
    video_generation_mode_enum.drop(op.get_bind())
