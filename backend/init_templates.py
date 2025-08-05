#!/usr/bin/env python3
"""
Overlay Template Initialization CLI for Timelapser v4.

This script provides a command-line interface for managing overlay templates
in fresh database deployments, particularly useful for Docker containers.
"""

import argparse
import json
import sys
from pathlib import Path


from app.database.template_initializer import (
    TemplateInitializationError,
    get_template_status,
    initialize_overlay_templates,
)

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Timelapser v4 Overlay Template Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s                    # Initialize overlay templates
    %(prog)s --status           # Check template status
    %(prog)s --status --json    # Status as JSON
        """,
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Check template status instead of initializing",
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument(
        "--database-url", help="Database connection URL (uses settings if not provided)"
    )

    args = parser.parse_args()

    try:
        if args.status:
            result = get_template_status(args.database_url)

            if args.json:
                print(json.dumps(result, indent=2))
            else:
                _print_template_status(result)
        else:
            result = initialize_overlay_templates(args.database_url)

            if args.json:
                print(json.dumps(result, indent=2))
            else:
                _print_initialization_result(result)

    except TemplateInitializationError as e:
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


def _print_initialization_result(result):
    """Print human-readable initialization results."""
    if result.get("success"):
        print(f"✅ {result['message']}")

        if result.get("templates_inserted", 0) > 0:
            print(f"   📄 Templates inserted: {result['templates_inserted']}")

        if result.get("templates_skipped", 0) > 0:
            print(f"   ⏭️  Templates skipped: {result['templates_skipped']}")
    else:
        print(
            f"⚠️ {result.get('message', 'Template initialization completed with errors')}"
        )

    if result.get("errors"):
        print("\n❌ Errors:")
        for error in result["errors"]:
            print(f"   • {error}")


def _print_template_status(result):
    """Print human-readable template status."""
    if result.get("error"):
        print(f"❌ Error: {result['error']}")
        return

    print("📊 Overlay Template Status")
    print("=" * 26)

    # File templates
    file_templates = result.get("file_templates", [])
    print(f"Template files found: {len(file_templates)}")

    if file_templates:
        print("\n📄 Template Files:")
        for template in file_templates:
            status = "✅" if template["name"] != "ERROR" else "❌"
            print(f"   {status} {template['file']}: {template['name']}")
            if template["name"] != "ERROR" and template.get("description"):
                print(f"      {template['description']}")

    # Database templates
    db_templates = result.get("db_templates", [])
    print(f"\nBuilt-in presets in database: {len(db_templates)}")

    if db_templates:
        print("\n🗄️  Database Templates:")
        for template in db_templates:
            print(f"   ✅ {template['name']}")
            if template.get("description"):
                print(f"      {template['description']}")
            if template.get("created_at"):
                print(f"      Created: {template['created_at']}")


if __name__ == "__main__":
    sys.exit(main())
