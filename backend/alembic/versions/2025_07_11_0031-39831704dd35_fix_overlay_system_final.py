"""fix_overlay_system_final

Revision ID: 39831704dd35
Revises: ee4dc446f0cd
Create Date: 2025-07-11 00:31:17.261454

"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "39831704dd35"
down_revision: Union[str, None] = "ee4dc446f0cd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create overlay system tables properly without postgresql_with issues"""

    connection = op.get_bind()

    # Drop any existing overlay tables first to start clean
    print("🧹 Cleaning up any existing overlay tables...")
    try:
        connection.execute(
            sa.text("DROP TABLE IF EXISTS overlay_generation_jobs CASCADE")
        )
        connection.execute(sa.text("DROP TABLE IF EXISTS overlay_assets CASCADE"))
        connection.execute(sa.text("DROP TABLE IF EXISTS timelapse_overlays CASCADE"))
        connection.execute(sa.text("DROP TABLE IF EXISTS overlay_presets CASCADE"))

        # Remove overlay columns from images if they exist
        connection.execute(
            sa.text("ALTER TABLE images DROP COLUMN IF EXISTS overlay_path")
        )
        connection.execute(
            sa.text("ALTER TABLE images DROP COLUMN IF EXISTS has_valid_overlay")
        )
        connection.execute(
            sa.text("ALTER TABLE images DROP COLUMN IF EXISTS overlay_updated_at")
        )

        print("✅ Existing overlay tables cleaned up")
    except Exception as e:
        print(f"⚠️ Cleanup warning: {e}")

    # Create overlay_presets table
    print("📋 Creating overlay_presets table...")
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
        print(f"❌ overlay_presets table creation failed: {e}")
        raise

    # Create timelapse_overlays table
    print("📋 Creating timelapse_overlays table...")
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
        print(f"❌ timelapse_overlays table creation failed: {e}")
        raise

    # Create overlay_assets table
    print("📋 Creating overlay_assets table...")
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
        print(f"❌ overlay_assets table creation failed: {e}")
        raise

    # Create overlay_generation_jobs table
    print("📋 Creating overlay_generation_jobs table...")
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
        print(f"❌ overlay_generation_jobs table creation failed: {e}")
        raise

    # Add overlay tracking columns to images table
    print("📸 Adding overlay tracking columns to images table...")
    try:
        op.add_column(
            "images",
            sa.Column(
                "overlay_path",
                sa.Text(),
                nullable=True,
                comment="Path to generated overlay image relative to data directory",
            ),
        )
        print("✅ Added overlay_path column to images table")

        op.add_column(
            "images",
            sa.Column(
                "has_valid_overlay",
                sa.Boolean(),
                nullable=False,
                server_default="false",
                comment="Whether this image has a valid generated overlay",
            ),
        )
        print("✅ Added has_valid_overlay column to images table")

        op.add_column(
            "images",
            sa.Column(
                "overlay_updated_at",
                sa.TIMESTAMP(timezone=True),
                nullable=True,
                comment="Timestamp when overlay was last generated",
            ),
        )
        print("✅ Added overlay_updated_at column to images table")
    except Exception as e:
        print(f"❌ Adding overlay columns failed: {e}")
        raise

    # Create performance indexes
    print("⚡ Creating performance indexes...")
    try:
        # GIN indexes for JSONB columns
        op.create_index(
            "idx_overlay_presets_config_gin",
            "overlay_presets",
            ["overlay_config"],
            postgresql_using="gin",
        )
        print("✅ Created GIN index on overlay_presets.overlay_config")

        op.create_index(
            "idx_timelapse_overlays_config_gin",
            "timelapse_overlays",
            ["overlay_config"],
            postgresql_using="gin",
        )
        print("✅ Created GIN index on timelapse_overlays.overlay_config")

        # Job queue indexes
        op.create_index(
            "idx_overlay_generation_jobs_active",
            "overlay_generation_jobs",
            ["priority", "created_at"],
            postgresql_include=["image_id", "job_type"],
            postgresql_where="status IN ('pending', 'processing')",
        )
        print("✅ Created partial index for active overlay generation jobs")

        op.create_index(
            "idx_overlay_generation_jobs_completed",
            "overlay_generation_jobs",
            ["completed_at"],
            postgresql_where="status IN ('completed', 'failed', 'cancelled')",
        )
        print("✅ Created partial index for completed overlay generation jobs")

        # Timelapse overlay indexes
        op.create_index(
            "idx_timelapse_overlays_active",
            "timelapse_overlays",
            ["timelapse_id"],
            postgresql_include=["preset_id", "enabled"],
            postgresql_where="enabled = TRUE",
        )
        print("✅ Created partial index for active timelapse overlays")

        # Asset indexes
        op.create_index(
            "idx_overlay_assets_images",
            "overlay_assets",
            ["mime_type"],
            postgresql_where="mime_type LIKE 'image/%'",
        )
        print("✅ Created partial index for image assets")

        # Built-in preset index
        op.create_index(
            "idx_overlay_presets_builtin",
            "overlay_presets",
            ["name"],
            postgresql_where="is_builtin = TRUE",
        )
        print("✅ Created partial index for built-in presets")

        # Image overlay indexes
        op.create_index("idx_images_has_valid_overlay", "images", ["has_valid_overlay"])
        print("✅ Created index on images.has_valid_overlay")

        op.create_index(
            "idx_images_overlay_updated_at", "images", ["overlay_updated_at"]
        )
        print("✅ Created index on images.overlay_updated_at")

    except Exception as e:
        print(f"❌ Index creation failed: {e}")
        raise

    # Seed built-in overlay presets
    print("🌱 Seeding built-in overlay presets...")
    try:
        presets = [
            {
                "name": "Basic Timestamp",
                "description": "Simple date and time overlay in bottom-right corner",
                "config": {
                    "overlay_items": [
                        {
                            "id": "timestamp_1",
                            "type": "date_time",
                            "position": "bottomRight",
                            "enabled": True,
                            "settings": {
                                "textSize": 24,
                                "textColor": "#FFFFFF",
                                "backgroundColor": "#000000",
                                "backgroundOpacity": 50,
                                "dateFormat": "%m/%d/%Y %H:%M:%S",
                            },
                        }
                    ],
                    "global_settings": {
                        "opacity": 100,
                        "font": "arial.ttf",
                        "x_margin": 20,
                        "y_margin": 20,
                        "background_color": "#000000",
                        "background_opacity": 50,
                        "fill_color": "#FFFFFF",
                        "drop_shadow": 2,
                    },
                },
            },
            {
                "name": "Weather + Time",
                "description": "Date, time, and weather information overlay",
                "config": {
                    "overlay_items": [
                        {
                            "id": "datetime_1",
                            "type": "date_time",
                            "position": "bottomLeft",
                            "enabled": True,
                            "settings": {
                                "textSize": 20,
                                "textColor": "#FFFFFF",
                                "backgroundColor": "#000000",
                                "backgroundOpacity": 60,
                                "dateFormat": "%m/%d/%Y %H:%M:%S",
                            },
                        },
                        {
                            "id": "weather_1",
                            "type": "weather_temp_conditions",
                            "position": "topRight",
                            "enabled": True,
                            "settings": {
                                "textSize": 18,
                                "textColor": "#FFFFFF",
                                "backgroundColor": "#1a472a",
                                "backgroundOpacity": 70,
                            },
                        },
                    ],
                    "global_settings": {
                        "opacity": 100,
                        "font": "arial.ttf",
                        "x_margin": 15,
                        "y_margin": 15,
                        "background_color": "#000000",
                        "background_opacity": 60,
                        "fill_color": "#FFFFFF",
                        "drop_shadow": 2,
                    },
                },
            },
            {
                "name": "Minimal",
                "description": "Clean date-only overlay",
                "config": {
                    "overlay_items": [
                        {
                            "id": "date_1",
                            "type": "date",
                            "position": "bottomCenter",
                            "enabled": True,
                            "settings": {
                                "textSize": 18,
                                "textColor": "#FFFFFF",
                                "backgroundColor": "#000000",
                                "backgroundOpacity": 40,
                                "dateFormat": "%B %d, %Y",
                            },
                        }
                    ],
                    "global_settings": {
                        "opacity": 90,
                        "font": "arial.ttf",
                        "x_margin": 20,
                        "y_margin": 15,
                        "background_color": "#000000",
                        "background_opacity": 40,
                        "fill_color": "#FFFFFF",
                        "drop_shadow": 2,
                    },
                },
            },
            {
                "name": "Complete Info",
                "description": "Comprehensive overlay with day counter, time, and weather",
                "config": {
                    "overlay_items": [
                        {
                            "id": "day_counter_1",
                            "type": "day_number",
                            "position": "topLeft",
                            "enabled": True,
                            "settings": {
                                "textSize": 28,
                                "textColor": "#FFFF00",
                                "backgroundColor": "#000000",
                                "backgroundOpacity": 80,
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
                                "backgroundColor": "#000000",
                                "backgroundOpacity": 60,
                                "dateFormat": "%m/%d/%Y %H:%M:%S",
                            },
                        },
                        {
                            "id": "weather_2",
                            "type": "weather_temp_conditions",
                            "position": "topRight",
                            "enabled": True,
                            "settings": {
                                "textSize": 16,
                                "textColor": "#FFFFFF",
                                "backgroundColor": "#1a472a",
                                "backgroundOpacity": 70,
                            },
                        },
                    ],
                    "global_settings": {
                        "opacity": 100,
                        "font": "arial.ttf",
                        "x_margin": 25,
                        "y_margin": 25,
                        "background_color": "#000000",
                        "background_opacity": 60,
                        "fill_color": "#FFFFFF",
                        "drop_shadow": 2,
                    },
                },
            },
        ]

        for preset in presets:
            connection.execute(
                sa.text(
                    """
                INSERT INTO overlay_presets (name, description, overlay_config, is_builtin)
                VALUES (:name, :description, :config, TRUE)
                ON CONFLICT (name) DO NOTHING
            """
                ),
                {
                    "name": preset["name"],
                    "description": preset["description"],
                    "config": json.dumps(preset["config"]),
                },
            )
            print(f"✅ Seeded built-in preset: {preset['name']}")

        print("✅ Built-in overlay presets seeding completed")
    except Exception as e:
        print(f"❌ Built-in presets seeding failed: {e}")
        raise

    print("🎉 Overlay system migration completed successfully!")


def downgrade() -> None:
    """Remove overlay system tables and columns"""

    print("🧹 Removing overlay system...")

    # Drop indexes first
    op.drop_index("idx_images_overlay_updated_at", "images")
    op.drop_index("idx_images_has_valid_overlay", "images")
    op.drop_index("idx_overlay_presets_builtin", "overlay_presets")
    op.drop_index("idx_overlay_assets_images", "overlay_assets")
    op.drop_index("idx_timelapse_overlays_active", "timelapse_overlays")
    op.drop_index("idx_overlay_generation_jobs_completed", "overlay_generation_jobs")
    op.drop_index("idx_overlay_generation_jobs_active", "overlay_generation_jobs")
    op.drop_index("idx_timelapse_overlays_config_gin", "timelapse_overlays")
    op.drop_index("idx_overlay_presets_config_gin", "overlay_presets")

    # Drop overlay columns from images
    op.drop_column("images", "overlay_updated_at")
    op.drop_column("images", "has_valid_overlay")
    op.drop_column("images", "overlay_path")

    # Drop tables in reverse dependency order
    op.drop_table("overlay_generation_jobs")
    op.drop_table("overlay_assets")
    op.drop_table("timelapse_overlays")
    op.drop_table("overlay_presets")

    print("✅ Overlay system removed")
