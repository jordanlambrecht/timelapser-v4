"""Create overlay system tables and infrastructure

Revision ID: 032_create_overlay_system
Revises: 031_add_camera_crop_settings
Create Date: 2025-01-10 15:00:00.000000

"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "032_create_overlay_system"
down_revision: Union[str, None] = "031_add_camera_crop_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create overlay system tables and infrastructure"""

    connection = op.get_bind()

    # Create overlay_presets table
    print("Creating overlay_presets table...")
    try:
        op.create_table(
            "overlay_presets",
            sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column(
                "overlay_config",
                postgresql.JSONB(),
                nullable=False,
                server_default="{}",
            ),
            sa.Column(
                "is_builtin", sa.Boolean(), nullable=False, server_default="false"
            ),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
            comment="System-wide overlay presets for timelapse configuration",
        )
        print("✅ overlay_presets table created")
    except Exception as e:
        print(f"⚠️ overlay_presets table creation skipped: {e}")

    # Create timelapse_overlays table
    print("Creating timelapse_overlays table...")
    try:
        op.create_table(
            "timelapse_overlays",
            sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
            sa.Column("timelapse_id", sa.Integer(), nullable=False),
            sa.Column("preset_id", sa.Integer(), nullable=True),
            sa.Column(
                "overlay_config",
                postgresql.JSONB(),
                nullable=False,
                server_default="{}",
            ),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.Column(
                "updated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.ForeignKeyConstraint(
                ["timelapse_id"], ["timelapses.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["preset_id"], ["overlay_presets.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "timelapse_id", name="uq_timelapse_overlays_timelapse_id"
            ),
            comment="Overlay configurations for individual timelapses",
        )
        print("✅ timelapse_overlays table created")
    except Exception as e:
        print(f"⚠️ timelapse_overlays table creation skipped: {e}")

    # Create overlay_assets table
    print("Creating overlay_assets table...")
    try:
        op.create_table(
            "overlay_assets",
            sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
            sa.Column("filename", sa.String(255), nullable=False),
            sa.Column("original_name", sa.String(255), nullable=False),
            sa.Column("file_path", sa.Text(), nullable=False),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("mime_type", sa.String(100), nullable=False),
            sa.Column(
                "uploaded_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.CheckConstraint(
                "file_size > 0 AND file_size <= 104857600",
                name="ck_overlay_assets_file_size",
            ),
            sa.CheckConstraint(
                "mime_type IN ('image/png', 'image/jpeg', 'image/webp')",
                name="ck_overlay_assets_mime_type",
            ),
            sa.PrimaryKeyConstraint("id"),
            comment="Uploaded watermark and logo assets for overlays",
        )
        print("✅ overlay_assets table created")
    except Exception as e:
        print(f"⚠️ overlay_assets table creation skipped: {e}")

    # Create overlay_generation_jobs table
    print("Creating overlay_generation_jobs table...")
    try:
        op.create_table(
            "overlay_generation_jobs",
            sa.Column("id", sa.Integer(), sa.Identity(always=True), nullable=False),
            sa.Column("image_id", sa.Integer(), nullable=False),
            sa.Column(
                "priority", sa.String(20), nullable=False, server_default="medium"
            ),
            sa.Column(
                "status", sa.String(20), nullable=False, server_default="pending"
            ),
            sa.Column(
                "job_type", sa.String(20), nullable=False, server_default="single"
            ),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                nullable=False,
                server_default=sa.text("NOW()"),
            ),
            sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.CheckConstraint(
                "priority IN ('low', 'medium', 'high')",
                name="ck_overlay_generation_jobs_priority",
            ),
            sa.CheckConstraint(
                "status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')",
                name="ck_overlay_generation_jobs_status",
            ),
            sa.CheckConstraint(
                "job_type IN ('single', 'batch', 'priority')",
                name="ck_overlay_generation_jobs_job_type",
            ),
            sa.CheckConstraint(
                "retry_count >= 0 AND retry_count <= 5",
                name="ck_overlay_generation_jobs_retry_count",
            ),
            sa.CheckConstraint(
                "(started_at IS NULL OR started_at >= created_at) AND (completed_at IS NULL OR completed_at >= COALESCE(started_at, created_at))",
                name="ck_overlay_generation_jobs_valid_timing",
            ),
            sa.ForeignKeyConstraint(["image_id"], ["images.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            comment="Job queue for overlay generation processing",
        )
        print("✅ overlay_generation_jobs table created")
    except Exception as e:
        print(f"⚠️ overlay_generation_jobs table creation skipped: {e}")

    # Add overlay tracking columns to images table
    print("Adding overlay tracking columns to images table...")

    # Check and add overlay_path column
    result = connection.execute(
        sa.text(
            """
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'images' AND column_name = 'overlay_path'
    """
        )
    )
    if not result.fetchone():
        op.add_column(
            "images",
            sa.Column(
                "overlay_path",
                sa.Text(),
                nullable=True,
                comment="Path to generated overlay image file",
            ),
        )
        print("✅ Added overlay_path column to images table")
    else:
        print("⚠️ overlay_path column already exists")

    # Check and add has_valid_overlay column
    result = connection.execute(
        sa.text(
            """
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'images' AND column_name = 'has_valid_overlay'
    """
        )
    )
    if not result.fetchone():
        op.add_column(
            "images",
            sa.Column(
                "has_valid_overlay",
                sa.Boolean(),
                nullable=False,
                server_default="false",
                comment="Whether image has successfully generated overlay",
            ),
        )
        print("✅ Added has_valid_overlay column to images table")
    else:
        print("⚠️ has_valid_overlay column already exists")

    # Check and add overlay_updated_at column
    result = connection.execute(
        sa.text(
            """
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'images' AND column_name = 'overlay_updated_at'
    """
        )
    )
    if not result.fetchone():
        op.add_column(
            "images",
            sa.Column(
                "overlay_updated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=True,
                comment="Timestamp of last overlay generation",
            ),
        )
        print("✅ Added overlay_updated_at column to images table")
    else:
        print("⚠️ overlay_updated_at column already exists")

    # Create performance indexes
    print("Creating performance indexes...")

    # GIN indexes for JSONB columns
    try:
        op.create_index(
            "idx_overlay_presets_config_gin",
            "overlay_presets",
            ["overlay_config"],
            postgresql_using="gin",
            if_not_exists=True,
        )
        print("✅ Created GIN index on overlay_presets.overlay_config")
    except Exception as e:
        print(f"⚠️ GIN index on overlay_presets.overlay_config skipped: {e}")

    try:
        op.create_index(
            "idx_timelapse_overlays_config_gin",
            "timelapse_overlays",
            ["overlay_config"],
            postgresql_using="gin",
            if_not_exists=True,
        )
        print("✅ Created GIN index on timelapse_overlays.overlay_config")
    except Exception as e:
        print(f"⚠️ GIN index on timelapse_overlays.overlay_config skipped: {e}")

    # Partial indexes for active jobs
    try:
        op.create_index(
            "idx_overlay_generation_jobs_active",
            "overlay_generation_jobs",
            ["priority", "created_at"],
            postgresql_include=["image_id", "job_type"],
            postgresql_where=sa.text("status IN ('pending', 'processing')"),
            if_not_exists=True,
        )
        print("✅ Created partial index for active overlay generation jobs")
    except Exception as e:
        print(f"⚠️ Active jobs index skipped: {e}")

    try:
        op.create_index(
            "idx_overlay_generation_jobs_completed",
            "overlay_generation_jobs",
            ["completed_at"],
            postgresql_where=sa.text("status IN ('completed', 'failed', 'cancelled')"),
            if_not_exists=True,
        )
        print("✅ Created partial index for completed overlay generation jobs")
    except Exception as e:
        print(f"⚠️ Completed jobs index skipped: {e}")

    # Index for active timelapse overlays
    try:
        op.create_index(
            "idx_timelapse_overlays_active",
            "timelapse_overlays",
            ["timelapse_id"],
            postgresql_include=["preset_id", "enabled"],
            postgresql_where=sa.text("enabled = TRUE"),
            if_not_exists=True,
        )
        print("✅ Created partial index for active timelapse overlays")
    except Exception as e:
        print(f"⚠️ Active timelapse overlays index skipped: {e}")

    # Partial indexes for common queries
    try:
        op.create_index(
            "idx_overlay_assets_images",
            "overlay_assets",
            ["mime_type"],
            postgresql_where=sa.text("mime_type LIKE 'image/%'"),
            if_not_exists=True,
        )
        print("✅ Created partial index for image assets")
    except Exception as e:
        print(f"⚠️ Image assets index skipped: {e}")

    try:
        op.create_index(
            "idx_overlay_presets_builtin",
            "overlay_presets",
            ["name"],
            postgresql_where=sa.text("is_builtin = TRUE"),
            if_not_exists=True,
        )
        print("✅ Created partial index for built-in presets")
    except Exception as e:
        print(f"⚠️ Built-in presets index skipped: {e}")

    # Indexes for images table overlay columns
    try:
        op.create_index(
            "idx_images_has_valid_overlay",
            "images",
            ["has_valid_overlay"],
            if_not_exists=True,
        )
        print("✅ Created index on images.has_valid_overlay")
    except Exception as e:
        print(f"⚠️ Images overlay validity index skipped: {e}")

    try:
        op.create_index(
            "idx_images_overlay_updated_at",
            "images",
            ["overlay_updated_at"],
            if_not_exists=True,
        )
        print("✅ Created index on images.overlay_updated_at")
    except Exception as e:
        print(f"⚠️ Images overlay timestamp index skipped: {e}")

    # Seed built-in overlay presets
    print("Seeding built-in overlay presets...")
    try:
        # Define built-in presets
        builtin_presets = [
            {
                "name": "Basic Timestamp",
                "description": "Simple date and time overlay in bottom-left corner",
                "overlay_config": {
                    "overlay_items": [
                        {
                            "id": "timestamp_1",
                            "type": "date_time",
                            "position": "bottomLeft",
                            "enabled": True,
                            "settings": {
                                "textSize": 16,
                                "textColor": "#FFFFFF",
                                "backgroundOpacity": 50,
                                "dateFormat": "MM/dd/yyyy HH:mm",
                            },
                        }
                    ],
                    "global_settings": {
                        "opacity": 100,
                        "font": "Arial",
                        "x_margin": 20,
                        "y_margin": 20,
                        "background_color": "#000000",
                        "background_opacity": 50,
                        "fill_color": "#FFFFFF",
                        "drop_shadow": 2,
                    },
                },
                "is_builtin": True,
            },
            {
                "name": "Weather + Time",
                "description": "Weather conditions with timestamp and temperature",
                "overlay_config": {
                    "overlay_items": [
                        {
                            "id": "weather_1",
                            "type": "weather_temp_conditions",
                            "position": "topLeft",
                            "enabled": True,
                            "settings": {
                                "textSize": 14,
                                "textColor": "#FFFFFF",
                                "backgroundOpacity": 40,
                            },
                        },
                        {
                            "id": "datetime_1",
                            "type": "date_time",
                            "position": "bottomLeft",
                            "enabled": True,
                            "settings": {
                                "textSize": 16,
                                "textColor": "#FFFFFF",
                                "backgroundOpacity": 50,
                                "dateFormat": "MM/dd/yyyy HH:mm",
                            },
                        },
                    ],
                    "global_settings": {
                        "opacity": 100,
                        "font": "Arial",
                        "x_margin": 20,
                        "y_margin": 20,
                        "background_color": "#000000",
                        "background_opacity": 45,
                        "fill_color": "#FFFFFF",
                        "drop_shadow": 2,
                    },
                },
                "is_builtin": True,
            },
            {
                "name": "Minimal",
                "description": "Just frame count in corner",
                "overlay_config": {
                    "overlay_items": [
                        {
                            "id": "frame_count_1",
                            "type": "frame_number",
                            "position": "bottomRight",
                            "enabled": True,
                            "settings": {
                                "textSize": 14,
                                "textColor": "#FFFFFF",
                                "backgroundOpacity": 30,
                            },
                        }
                    ],
                    "global_settings": {
                        "opacity": 100,
                        "font": "Arial",
                        "x_margin": 15,
                        "y_margin": 15,
                        "background_color": "#000000",
                        "background_opacity": 30,
                        "fill_color": "#FFFFFF",
                        "drop_shadow": 1,
                    },
                },
                "is_builtin": True,
            },
            {
                "name": "Complete Info",
                "description": "Comprehensive overlay with multiple data points",
                "overlay_config": {
                    "overlay_items": [
                        {
                            "id": "timelapse_name_1",
                            "type": "timelapse_name",
                            "position": "topLeft",
                            "enabled": True,
                            "settings": {
                                "textSize": 18,
                                "textColor": "#FFFFFF",
                                "backgroundOpacity": 60,
                            },
                        },
                        {
                            "id": "weather_2",
                            "type": "weather_temp_conditions",
                            "position": "topRight",
                            "enabled": True,
                            "settings": {
                                "textSize": 14,
                                "textColor": "#FFFFFF",
                                "backgroundOpacity": 40,
                            },
                        },
                        {
                            "id": "datetime_2",
                            "type": "date_time",
                            "position": "bottomLeft",
                            "enabled": True,
                            "settings": {
                                "textSize": 16,
                                "textColor": "#FFFFFF",
                                "backgroundOpacity": 50,
                                "dateFormat": "MM/dd/yyyy HH:mm",
                            },
                        },
                        {
                            "id": "frame_count_2",
                            "type": "frame_number",
                            "position": "bottomRight",
                            "enabled": True,
                            "settings": {
                                "textSize": 14,
                                "textColor": "#FFFFFF",
                                "backgroundOpacity": 30,
                            },
                        },
                    ],
                    "global_settings": {
                        "opacity": 100,
                        "font": "Arial",
                        "x_margin": 20,
                        "y_margin": 20,
                        "background_color": "#000000",
                        "background_opacity": 45,
                        "fill_color": "#FFFFFF",
                        "drop_shadow": 2,
                    },
                },
                "is_builtin": True,
            },
        ]

        # Insert built-in presets
        for preset in builtin_presets:
            # Check if preset already exists
            result = connection.execute(
                sa.text("SELECT id FROM overlay_presets WHERE name = :name"),
                {"name": preset["name"]},
            )

            if not result.fetchone():
                connection.execute(
                    sa.text(
                        """INSERT INTO overlay_presets (name, description, overlay_config, is_builtin) 
                       VALUES (:name, :description, :overlay_config, :is_builtin)"""
                    ),
                    {
                        "name": preset["name"],
                        "description": preset["description"],
                        "overlay_config": json.dumps(preset["overlay_config"]),
                        "is_builtin": preset["is_builtin"],
                    },
                )
                print(f"✅ Seeded built-in preset: {preset['name']}")
            else:
                print(f"⚠️ Built-in preset already exists: {preset['name']}")

        connection.commit()
        print("✅ Built-in overlay presets seeding completed")
    except Exception as e:
        print(f"⚠️ Built-in presets seeding failed: {e}")
        connection.rollback()

    print("🎉 Overlay system migration completed successfully!")


def downgrade() -> None:
    """Remove overlay system tables and infrastructure"""

    print("Removing overlay system infrastructure...")

    # Drop indexes
    indexes_to_drop = [
        ("idx_images_overlay_updated_at", "images"),
        ("idx_images_has_valid_overlay", "images"),
        ("idx_overlay_presets_builtin", "overlay_presets"),
        ("idx_overlay_assets_images", "overlay_assets"),
        ("idx_timelapse_overlays_active", "timelapse_overlays"),
        ("idx_overlay_generation_jobs_completed", "overlay_generation_jobs"),
        ("idx_overlay_generation_jobs_active", "overlay_generation_jobs"),
        ("idx_timelapse_overlays_config_gin", "timelapse_overlays"),
        ("idx_overlay_presets_config_gin", "overlay_presets"),
    ]

    for index_name, table_name in indexes_to_drop:
        try:
            op.drop_index(index_name, table_name=table_name)
            print(f"✅ Dropped index: {index_name}")
        except Exception as e:
            print(f"⚠️ Index drop skipped: {index_name} - {e}")

    # Drop columns from images table
    columns_to_drop = ["overlay_updated_at", "has_valid_overlay", "overlay_path"]
    for column in columns_to_drop:
        try:
            op.drop_column("images", column)
            print(f"✅ Dropped column: images.{column}")
        except Exception as e:
            print(f"⚠️ Column drop skipped: images.{column} - {e}")

    # Drop tables in reverse dependency order
    tables_to_drop = [
        "overlay_generation_jobs",
        "timelapse_overlays",
        "overlay_assets",
        "overlay_presets",
    ]

    for table in tables_to_drop:
        try:
            op.drop_table(table)
            print(f"✅ Dropped table: {table}")
        except Exception as e:
            print(f"⚠️ Table drop skipped: {table} - {e}")

    print("🧹 Overlay system infrastructure removed")
