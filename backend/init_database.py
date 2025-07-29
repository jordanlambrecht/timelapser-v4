#!/usr/bin/env python3
"""
Database initialization CLI for Timelapser v4.

This script provides a command-line interface for database initialization
and status checking.
"""

import argparse
import json
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.database.migrations import (
    initialize_database,
    get_database_status,
    DatabaseInitializationError,
)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Timelapser v4 Database Initialization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Initialize database
  %(prog)s --status           # Check database status
  %(prog)s --status --json    # Status as JSON
        """,
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Check database status instead of initializing",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    try:
        if args.status:
            status = get_database_status()

            if args.json:
                print(json.dumps(status, indent=2))
            else:
                _print_status(status)
        else:
            result = initialize_database()

            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"✅ {result['message']} (method: {result['method']})")

    except DatabaseInitializationError as e:
        if args.json:
            print(json.dumps({"error": str(e), "success": False}))
        else:
            print(f"❌ {e}")
        return 1
    except Exception as e:
        if args.json:
            print(json.dumps({"error": f"Unexpected error: {e}", "success": False}))
        else:
            print(f"❌ Unexpected error: {e}")
        return 1

    return 0


def _print_status(status):
    """Print human-readable status information."""
    if status.get("error"):
        print(f"❌ Error: {status['error']}")
        return

    print("📊 Database Status")
    print("=" * 18)
    print(f"Fresh database: {status.get('is_fresh', 'unknown')}")
    print(f"Schema file exists: {status.get('schema_file_exists', 'unknown')}")

    if status.get("schema_file_size"):
        size_kb = status["schema_file_size"] / 1024
        print(f"Schema file size: {size_kb:.1f} KB")

    if not status.get("is_fresh"):
        print(f"Current revision: {status.get('current_revision', 'unknown')}")
        print(f"Head revision: {status.get('head_revision', 'unknown')}")
        print(f"Up to date: {status.get('up_to_date', 'unknown')}")

    if status.get("revision_error"):
        print(f"Revision check error: {status['revision_error']}")


if __name__ == "__main__":
    sys.exit(main())
