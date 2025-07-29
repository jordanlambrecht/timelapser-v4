"""
Database schema management for fresh deployments and migrations.

This module handles database initialization with a hybrid approach:
- Fresh databases: Direct schema creation from SQL file
- Existing databases: Standard Alembic migrations
"""

import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from loguru import logger
import psycopg

from ..config import settings


class DatabaseSchemaError(Exception):
    """Base exception for database schema operations."""

    pass


class SchemaFileNotFoundError(DatabaseSchemaError):
    """Raised when the schema SQL file cannot be found."""

    pass


class AlembicError(DatabaseSchemaError):
    """Raised when Alembic operations fail."""

    pass


class SchemaManager:
    """Manages database schema creation and migration detection."""

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize SchemaManager.

        Args:
            database_url: Database connection URL. Uses settings.database_url if None.
        """
        self.database_url = database_url or settings.database_url
        self._schema_file_path = self._locate_schema_file()

    def _locate_schema_file(self) -> Path:
        """Locate the current schema SQL file."""
        backend_root = Path(__file__).parent.parent.parent
        schema_path = backend_root / "schemas" / "current_schema.sql"

        if not schema_path.exists():
            raise SchemaFileNotFoundError(
                f"Schema file not found at {schema_path}. "
                "Generate it with: pg_dump $DATABASE_URL --schema-only > schemas/current_schema.sql"
            )

        return schema_path

    def is_fresh_database(self) -> bool:
        """
        Check if database is fresh (no existing Alembic state).

        Returns:
            True if database is fresh, False if it has existing migrations

        Raises:
            DatabaseSchemaError: If database connection or query fails
        """
        try:
            with psycopg.connect(self.database_url) as conn:
                with conn.cursor() as cur:
                    # Check if alembic_version table exists
                    cur.execute(
                        """
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = 'alembic_version'
                        )
                    """
                    )
                    result = cur.fetchone()
                    if result is None:
                        raise DatabaseSchemaError(
                            "Failed to check for alembic_version table"
                        )
                    table_exists = result[0]

                    if not table_exists:
                        logger.info("Fresh database: no alembic_version table")
                        return True

                    # Check if table has migration data
                    cur.execute("SELECT COUNT(*) FROM alembic_version")
                    result = cur.fetchone()
                    if result is None:
                        raise DatabaseSchemaError(
                            "Failed to count alembic_version records"
                        )
                    count = result[0]

                    if count == 0:
                        logger.info("Fresh database: empty alembic_version table")
                        return True

                    # Get current revision for logging
                    cur.execute("SELECT version_num FROM alembic_version")
                    result = cur.fetchone()
                    if result is None:
                        raise DatabaseSchemaError("Failed to get current revision")
                    revision = result[0]
                    logger.info(f"Existing database: revision {revision}")
                    return False

        except psycopg.Error as e:
            raise DatabaseSchemaError(f"Database connection failed: {e}") from e

    def create_fresh_schema(self) -> None:
        """
        Create database schema from SQL file for fresh databases.

        Raises:
            DatabaseSchemaError: If schema creation fails
        """
        try:
            logger.info("Creating fresh schema from SQL file")

            with open(self._schema_file_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()

            with psycopg.connect(self.database_url) as conn:
                # Use autocommit for DDL statements
                conn.autocommit = True
                with conn.cursor() as cur:
                    # For schema files with dynamic content, we need to use the raw execute
                    # psycopg3 allows this for DDL when using autocommit
                    # Split SQL into individual statements and execute each
                    statements = [
                        stmt.strip() for stmt in schema_sql.split(";") if stmt.strip()
                    ]
                    for statement in statements:
                        if statement:  # Skip empty statements
                            # Use bytes to bypass LiteralString requirement
                            cur.execute(statement.encode("utf-8"))

            logger.info("Fresh schema created successfully")

        except psycopg.Error as e:
            raise DatabaseSchemaError(f"Schema creation failed: {e}") from e
        except IOError as e:
            raise SchemaFileNotFoundError(f"Cannot read schema file: {e}") from e

    def get_current_revision(self) -> str:
        """
        Get current HEAD revision from Alembic.

        Returns:
            Current HEAD revision string

        Raises:
            AlembicError: If Alembic command fails
        """
        try:
            result = subprocess.run(
                ["alembic", "heads", "--resolve-dependencies"],
                cwd=Path(__file__).parent.parent.parent,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )

            # Parse revision from output
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    revision = line.split()[0]
                    if revision:
                        logger.debug(f"Current HEAD revision: {revision}")
                        return revision

            raise AlembicError("Could not parse revision from alembic output")

        except subprocess.CalledProcessError as e:
            raise AlembicError(f"Alembic heads command failed: {e.stderr}") from e
        except subprocess.TimeoutExpired:
            raise AlembicError("Alembic heads command timed out") from None

    def stamp_current_revision(self) -> None:
        """
        Mark database as current revision without running migrations.

        Raises:
            AlembicError: If stamp operation fails
        """
        try:
            current_revision = self.get_current_revision()
            logger.info(f"Stamping database with revision: {current_revision}")

            subprocess.run(
                ["alembic", "stamp", current_revision],
                cwd=Path(__file__).parent.parent.parent,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )

            logger.info("Database stamped successfully")

        except subprocess.CalledProcessError as e:
            raise AlembicError(f"Alembic stamp failed: {e.stderr}") from e
        except subprocess.TimeoutExpired:
            raise AlembicError("Alembic stamp timed out") from None

    def run_migrations(self) -> None:
        """
        Run Alembic migrations for existing databases.

        Raises:
            AlembicError: If migration fails
        """
        try:
            logger.info("Running Alembic migrations")

            subprocess.run(
                ["alembic", "upgrade", "head"],
                cwd=Path(__file__).parent.parent.parent,
                check=True,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes for migrations
            )

            logger.info("Migrations completed successfully")

        except subprocess.CalledProcessError as e:
            raise AlembicError(f"Migration failed: {e.stderr}") from e
        except subprocess.TimeoutExpired:
            raise AlembicError("Migration timed out after 5 minutes") from None

    def get_database_info(self) -> Dict[str, Any]:
        """
        Get database state information for diagnostics.

        Returns:
            Dictionary with database state info
        """
        try:
            info = {
                "is_fresh": self.is_fresh_database(),
                "schema_file_exists": self._schema_file_path.exists(),
                "schema_file_size": (
                    self._schema_file_path.stat().st_size
                    if self._schema_file_path.exists()
                    else 0
                ),
            }

            if not info["is_fresh"]:
                try:
                    with psycopg.connect(self.database_url) as conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT version_num FROM alembic_version")
                            result = cur.fetchone()
                            info["current_revision"] = (
                                result[0] if result is not None else None
                            )

                    info["head_revision"] = self.get_current_revision()
                    info["up_to_date"] = (
                        info["current_revision"] == info["head_revision"]
                    )

                except Exception as e:
                    info["revision_error"] = str(e)

            return info

        except Exception as e:
            return {"error": str(e), "is_fresh": None}
