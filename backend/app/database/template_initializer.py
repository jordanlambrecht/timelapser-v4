"""
Template Initializer for Overlay Presets

Handles initialization of built-in overlay templates for fresh database deployments.
This is designed to work with Docker deployments where the database is created from scratch.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg

from ..config import settings


class TemplateInitializationError(Exception):
    """Raised when template initialization fails."""

    pass


class OverlayTemplateInitializer:
    """
    Initializes built-in overlay templates in fresh database deployments.

    This service loads template JSON files and inserts them as built-in presets
    into the overlay_presets table after schema creation.
    """

    def __init__(self, database_url: Optional[str] = None) -> None:
        """
        Initialize template initializer.

        Args:
            database_url: Database connection URL. Uses settings if None.
        """
        self.database_url = database_url or settings.database_url
        self._templates_dir = Path(__file__).parent / "templates"

    def get_template_files(self) -> List[Path]:
        """
        Get list of template JSON files.

        Returns:
            List of template file paths
        """
        if not self._templates_dir.exists():
            return []

        return list(self._templates_dir.glob("*.json"))

    def load_template(self, template_path: Path) -> Dict[str, Any]:
        """
        Load and validate template from JSON file.

        Args:
            template_path: Path to template JSON file

        Returns:
            Template configuration dictionary

        Raises:
            TemplateInitializationError: If template loading fails
        """
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template = json.load(f)

            # Validate required fields
            required_fields = ["name", "description", "overlay_config", "is_builtin"]
            for field in required_fields:
                if field not in template:
                    raise TemplateInitializationError(
                        f"Template {template_path.name} missing required field: {field}"
                    )

            # Validate overlay_config structure
            overlay_config = template["overlay_config"]
            if not isinstance(overlay_config, dict):
                raise TemplateInitializationError(
                    f"Template {template_path.name} has invalid overlay_config"
                )

            if "overlayPositions" not in overlay_config:
                raise TemplateInitializationError(
                    f"Template {template_path.name} missing overlayPositions in overlay_config"
                )

            if "globalOptions" not in overlay_config:
                raise TemplateInitializationError(
                    f"Template {template_path.name} missing globalOptions in overlay_config"
                )

            return template

        except json.JSONDecodeError as e:
            raise TemplateInitializationError(
                f"Invalid JSON in template {template_path.name}: {e}"
            ) from e
        except IOError as e:
            raise TemplateInitializationError(
                f"Cannot read template {template_path.name}: {e}"
            ) from e

    def template_exists(self, conn, template_name: str) -> bool:
        """
        Check if template already exists in database.

        Args:
            conn: Database connection
            template_name: Name of template to check

        Returns:
            True if template exists, False otherwise
        """
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM overlay_presets WHERE name = %s", (template_name,)
                )
                return cur.fetchone() is not None
        except psycopg.Error as e:
            raise TemplateInitializationError(
                f"Failed to check template existence: {e}"
            ) from e

    def insert_template(self, conn, template: Dict[str, Any]) -> int:
        """
        Insert template into database.

        Args:
            conn: Database connection
            template: Template configuration

        Returns:
            ID of inserted template

        Raises:
            TemplateInitializationError: If insertion fails
        """
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO overlay_presets (name, description, overlay_config, is_builtin)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        template["name"],
                        template["description"],
                        json.dumps(template["overlay_config"]),
                        template["is_builtin"],
                    ),
                )
                result = cur.fetchone()
                if result is None:
                    raise TemplateInitializationError("Failed to insert template")
                return result[0]

        except psycopg.Error as e:
            raise TemplateInitializationError(
                f"Failed to insert template {template['name']}: {e}"
            ) from e

    def initialize_templates(self) -> Dict[str, Any]:
        """
        Initialize all overlay templates in the database.

        Returns:
            Dictionary with initialization results

        Raises:
            TemplateInitializationError: If initialization fails
        """
        template_files = self.get_template_files()

        if not template_files:
            return {
                "success": True,
                "message": "No template files found",
                "templates_inserted": 0,
                "templates_skipped": 0,
            }

        inserted_count = 0
        skipped_count = 0
        errors = []

        try:
            with psycopg.connect(self.database_url) as conn:
                conn.autocommit = False  # Use transactions

                for template_file in template_files:
                    try:
                        # Load template
                        template = self.load_template(template_file)

                        # Check if already exists
                        if self.template_exists(conn, template["name"]):
                            skipped_count += 1
                            continue

                        # Insert template
                        template_id = self.insert_template(conn, template)
                        inserted_count += 1

                    except TemplateInitializationError as e:
                        errors.append(f"{template_file.name}: {e}")
                        continue

                # Commit all insertions
                conn.commit()

        except psycopg.Error as e:
            raise TemplateInitializationError(f"Database connection failed: {e}") from e

        result = {
            "success": len(errors) == 0,
            "templates_inserted": inserted_count,
            "templates_skipped": skipped_count,
            "total_templates": len(template_files),
        }

        if inserted_count > 0:
            result["message"] = (
                f"Successfully initialized {inserted_count} overlay templates"
            )
        elif skipped_count > 0:
            result["message"] = f"All {skipped_count} templates already exist"
        else:
            result["message"] = "No templates processed"

        if errors:
            result["errors"] = errors
            if not result["success"]:
                result["message"] = (
                    f"Template initialization completed with {len(errors)} errors"
                )

        return result

    def get_template_status(self) -> Dict[str, Any]:
        """
        Get status of template files and database presets.

        Returns:
            Dictionary with template status information
        """
        try:
            template_files = self.get_template_files()
            file_templates = []

            # Load template info from files
            for template_file in template_files:
                try:
                    template = self.load_template(template_file)
                    file_templates.append(
                        {
                            "file": template_file.name,
                            "name": template["name"],
                            "description": template["description"],
                        }
                    )
                except TemplateInitializationError:
                    file_templates.append(
                        {
                            "file": template_file.name,
                            "name": "ERROR",
                            "description": "Failed to load template",
                        }
                    )

            # Check database presets
            db_templates = []
            try:
                with psycopg.connect(self.database_url) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT name, description, is_builtin, created_at
                            FROM overlay_presets
                            WHERE is_builtin = true
                            ORDER BY name
                            """
                        )
                        rows = cur.fetchall()
                        for row in rows:
                            db_templates.append(
                                {
                                    "name": row[0],
                                    "description": row[1],
                                    "is_builtin": row[2],
                                    "created_at": (
                                        row[3].isoformat() if row[3] else None
                                    ),
                                }
                            )
            except psycopg.Error as e:
                return {
                    "error": f"Database connection failed: {e}",
                    "file_templates": file_templates,
                    "db_templates": [],
                }

            return {
                "file_templates": file_templates,
                "db_templates": db_templates,
                "template_files_count": len(template_files),
                "db_builtin_count": len(db_templates),
            }

        except Exception as e:
            return {
                "error": f"Status check failed: {e}",
                "file_templates": [],
                "db_templates": [],
            }


def initialize_overlay_templates(database_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to initialize overlay templates.

    Args:
        database_url: Database connection URL. Uses settings if None.

    Returns:
        Dictionary with initialization results
    """
    initializer = OverlayTemplateInitializer(database_url)
    return initializer.initialize_templates()


def get_template_status(database_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to get template status.

    Args:
        database_url: Database connection URL. Uses settings if None.

    Returns:
        Dictionary with template status
    """
    initializer = OverlayTemplateInitializer(database_url)
    return initializer.get_template_status()
