"""
Database initialization orchestrator for Timelapser v4.

Handles database initialization with hybrid approach:
- Fresh databases: Direct schema creation
- Existing databases: Alembic migrations
"""

import sys
from typing import Dict, Any, Optional
from loguru import logger

from .schema_manager import SchemaManager, DatabaseSchemaError, AlembicError


class DatabaseInitializationError(Exception):
    """Raised when database initialization fails."""

    pass


def initialize_database(database_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Initialize database using hybrid approach.

    Args:
        database_url: Database connection URL. Uses settings if None.

    Returns:
        Dictionary with initialization results

    Raises:
        DatabaseInitializationError: If initialization fails
    """
    try:
        schema_manager = SchemaManager(database_url)

        if schema_manager.is_fresh_database():
            return _initialize_fresh_database(schema_manager)
        else:
            return _upgrade_existing_database(schema_manager)

    except DatabaseSchemaError as e:
        raise DatabaseInitializationError(f"Database initialization failed: {e}") from e
    except Exception as e:
        raise DatabaseInitializationError(
            f"Unexpected error during initialization: {e}"
        ) from e


def _initialize_fresh_database(schema_manager: SchemaManager) -> Dict[str, Any]:
    """Initialize fresh database with schema creation."""
    logger.info("Initializing fresh database")

    try:
        schema_manager.create_fresh_schema()
        schema_manager.stamp_current_revision()

        return {
            "method": "fresh_schema",
            "success": True,
            "message": "Fresh database initialized successfully",
        }

    except (DatabaseSchemaError, AlembicError) as e:
        raise DatabaseInitializationError(
            f"Fresh database initialization failed: {e}"
        ) from e


def _upgrade_existing_database(schema_manager: SchemaManager) -> Dict[str, Any]:
    """Upgrade existing database with migrations."""
    logger.info("Upgrading existing database")

    try:
        schema_manager.run_migrations()

        return {
            "method": "migrations",
            "success": True,
            "message": "Database upgraded successfully",
        }

    except AlembicError as e:
        raise DatabaseInitializationError(f"Database upgrade failed: {e}") from e


def get_database_status(database_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Get database status for health checks.

    Args:
        database_url: Database connection URL. Uses settings if None.

    Returns:
        Dictionary with database status
    """
    try:
        schema_manager = SchemaManager(database_url)
        return schema_manager.get_database_info()
    except Exception as e:
        return {"error": str(e), "status": "unhealthy"}


# CLI interface
def main():
    """CLI entry point for database initialization."""
    import sys

    try:
        result = initialize_database()
        print(f"✅ {result['message']} (method: {result['method']})")
        return 0
    except DatabaseInitializationError as e:
        print(f"❌ {e}")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
