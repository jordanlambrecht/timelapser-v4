#!/usr/bin/env python3
"""
Comprehensive test runner for database operations.

Runs all database tests and provides coverage summary for our optimizations.
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str]) -> tuple[int, str]:
    """Run a command and return exit code and output."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=Path(__file__).parent
        )
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return 1, str(e)


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 60}")
    print(f" {title}")
    print("=" * 60)


def main():
    """Run comprehensive database operations tests."""
    print("🚀 Running Database Operations Test Suite")
    print("Testing our database optimizations and patterns")

    # Test commands to run
    test_commands = [
        {
            "name": "Corruption Query Builder Tests",
            "cmd": [
                "python3",
                "-m",
                "pytest",
                "tests/database/test_corruption_query_builder.py",
                "-v",
            ],
            "description": "SQL generation, parameterization, performance patterns",
        },
        {
            "name": "Camera Operations Tests",
            "cmd": [
                "python3",
                "-m",
                "pytest",
                "tests/database/test_camera_operations.py",
                "-v",
            ],
            "description": "Caching, collection ETags, batch operations",
        },
        {
            "name": "Image Operations Tests",
            "cmd": [
                "python3",
                "-m",
                "pytest",
                "tests/database/test_image_operations.py",
                "-v",
            ],
            "description": "Collection ETags, batch processing, statistics",
        },
    ]

    # Summary counters
    total_passed = 0
    total_failed = 0
    total_skipped = 0
    failed_tests = []

    # Run each test suite
    for test in test_commands:
        print_section(test["name"])
        print(f"📋 Testing: {test['description']}")
        print(f"🔧 Command: {' '.join(test['cmd'])}")

        exit_code, output = run_command(test["cmd"])

        if exit_code == 0:
            print("✅ PASSED")
        else:
            print("❌ FAILED")
            failed_tests.append(test["name"])

        # Parse pytest output for counts
        lines = output.split("\n")
        for line in lines:
            if "passed" in line and ("failed" in line or "skipped" in line):
                # Parse line like "13 passed, 2 skipped in 0.07s"
                parts = line.strip().split()
                for i, part in enumerate(parts):
                    if part == "passed":
                        total_passed += int(parts[i - 1])
                    elif part == "failed":
                        total_failed += int(parts[i - 1])
                    elif part == "skipped":
                        total_skipped += int(parts[i - 1])

        # Show recent output (last few lines)
        output_lines = output.strip().split("\n")
        if len(output_lines) > 5:
            print("\n📊 Recent output:")
            for line in output_lines[-5:]:
                if line.strip():
                    print(f"   {line}")

    # Run all tests together for final summary
    print_section("Complete Test Suite")
    print("🔄 Running all database tests together...")

    exit_code, output = run_command(
        ["python3", "-m", "pytest", "tests/database/", "-v", "--tb=short"]
    )

    # Final summary
    print_section("Test Results Summary")

    if exit_code == 0:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️  Some tests failed")

    print(f"\n📈 Test Statistics:")
    print(f"   ✅ Passed:  {total_passed}")
    print(f"   ❌ Failed:  {total_failed}")
    print(f"   ⏭️  Skipped: {total_skipped}")
    print(f"   📊 Total:   {total_passed + total_failed + total_skipped}")

    if failed_tests:
        print(f"\n❌ Failed Test Suites:")
        for test in failed_tests:
            print(f"   - {test}")

    # Show what we're testing
    print_section("What We're Validating")
    validations = [
        "✅ Query Builders - SQL generation and parameterization",
        "✅ Caching Decorators - @cached_response application",
        "✅ Collection ETags - generate_collection_etag support",
        "✅ Time Management - utc_now() usage instead of NOW()",
        "✅ Performance Patterns - JOINs, batch operations, indexing",
        "✅ SQL Injection Protection - Proper parameterization",
        "✅ Error Handling - Database failure scenarios",
        "✅ Data Processing - Model conversion and filtering",
    ]

    for validation in validations:
        print(f"   {validation}")

    print(f"\n🏗️  Database Optimizations Tested:")
    optimizations = [
        "• Sophisticated caching with TTL management",
        "• ETag-aware cache invalidation patterns",
        "• Centralized query builders for consistency",
        "• Collection ETag support for list endpoints",
        "• Centralized time management with utc_now()",
        "• Batch operations for better performance",
        "• Proper async/sync patterns with psycopg3",
    ]

    for opt in optimizations:
        print(f"   {opt}")

    # Show how to run specific tests
    print_section("Running Specific Tests")
    print("🔧 Useful commands:")
    print("   # Run all database tests:")
    print("   python3 -m pytest tests/database/ -v")
    print("")
    print("   # Run with coverage:")
    print("   python3 -m pytest tests/database/ --cov=app.database --cov-report=html")
    print("")
    print("   # Run only unit tests (skip integration):")
    print("   python3 -m pytest tests/database/ -v -m 'not integration'")
    print("")
    print("   # Run only caching tests:")
    print("   python3 -m pytest tests/database/ -v -m 'caching'")
    print("")
    print("   # Run specific test file:")
    print("   python3 -m pytest tests/database/test_corruption_query_builder.py -v")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
