#!/usr/bin/env python3
# backend/run_tests.py
"""
Test runner script for the timelapser backend.

Provides convenient commands to run different test suites.
"""

import sys
import subprocess
from pathlib import Path
from typing import List, Optional


def run_command(cmd: List[str], cwd: Optional[Path] = None) -> int:
    """Run a command and return the exit code."""
    print(f"🏃 Running: {' '.join(cmd)}")
    if cwd:
        print(f"📁 Working directory: {cwd}")

    result = subprocess.run(cmd, cwd=cwd)
    return result.returncode


def run_cache_tests() -> int:
    """Run cache-related tests."""
    cmd = [
        "python",
        "-m",
        "pytest",
        "tests/test_cache_manager.py",
        "tests/test_cache_invalidation.py",
        "-v",
        "--tb=short",
    ]
    return run_command(cmd, Path(__file__).parent)


def run_all_tests() -> int:
    """Run all tests."""
    cmd = ["python", "-m", "pytest", "tests/", "-v", "--tb=short"]
    return run_command(cmd, Path(__file__).parent)


def run_tests_with_coverage() -> int:
    """Run tests with coverage report."""
    cmd = [
        "python",
        "-m",
        "pytest",
        "tests/",
        "--cov=app",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
        "-v",
    ]
    return run_command(cmd, Path(__file__).parent)


def run_thumbnail_tests() -> int:
    """Run thumbnail-related tests."""
    cmd = [
        "python",
        "-m",
        "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "-m",
        "thumbnail",
    ]
    return run_command(cmd, Path(__file__).parent)


def run_thumbnail_unit_tests() -> int:
    """Run thumbnail unit tests only."""
    cmd = [
        "python",
        "-m",
        "pytest",
        "tests/unit/",
        "-v",
        "--tb=short",
        "-m",
        "thumbnail",
    ]
    return run_command(cmd, Path(__file__).parent)


def run_thumbnail_coverage() -> int:
    """Run thumbnail tests with coverage report."""
    cmd = [
        "python",
        "-m",
        "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "-m",
        "thumbnail",
        "--cov=app.workers.thumbnail_worker",
        "--cov=app.services.thumbnail_service",
        "--cov=app.services.thumbnail_verification_service",
        "--cov=app.database.thumbnail_job_operations",
        "--cov-report=term-missing",
        "--cov-report=html:htmlcov",
    ]
    return run_command(cmd, Path(__file__).parent)


def run_thumbnail_frontend_tests() -> int:
    """Run thumbnail frontend integration tests."""
    cmd = [
        "python3",
        "-m",
        "pytest",
        "tests/frontend_integration/",
        "-v",
        "--tb=short",
        "-m",
        "frontend and thumbnail",
    ]
    return run_command(cmd, Path(__file__).parent)


def run_integration_tests() -> int:
    """Run integration tests."""
    cmd = [
        "python3",
        "-m",
        "pytest",
        "tests/integration/",
        "-v",
        "--tb=short",
        "-m",
        "integration",
    ]
    return run_command(cmd, Path(__file__).parent)


def install_test_dependencies() -> int:
    """Install test dependencies."""
    cmd = ["pip", "install", "pytest", "pytest-asyncio", "pytest-cov"]
    return run_command(cmd)


def main():
    """Main test runner."""
    if len(sys.argv) < 2:
        print("Usage: python run_tests.py [cache|all|coverage|thumbnail|thumbnail-unit|thumbnail-coverage|thumbnail-frontend|integration|install]")
        print()
        print("Commands:")
        print("  cache             - Run cache-related tests")
        print("  all               - Run all tests")
        print("  coverage          - Run tests with coverage report")
        print("  thumbnail         - Run all thumbnail-related tests")
        print("  thumbnail-unit    - Run thumbnail unit tests only")
        print("  thumbnail-coverage - Run thumbnail tests with coverage")
        print("  thumbnail-frontend - Run thumbnail frontend integration tests")
        print("  integration       - Run integration tests")
        print("  install           - Install test dependencies")
        sys.exit(1)

    command = sys.argv[1]

    if command == "cache":
        exit_code = run_cache_tests()
    elif command == "all":
        exit_code = run_all_tests()
    elif command == "coverage":
        exit_code = run_tests_with_coverage()
    elif command == "thumbnail":
        exit_code = run_thumbnail_tests()
    elif command == "thumbnail-unit":
        exit_code = run_thumbnail_unit_tests()
    elif command == "thumbnail-coverage":
        exit_code = run_thumbnail_coverage()
    elif command == "thumbnail-frontend":
        exit_code = run_thumbnail_frontend_tests()
    elif command == "integration":
        exit_code = run_integration_tests()
    elif command == "install":
        exit_code = install_test_dependencies()
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)

    if exit_code == 0:
        print("✅ Tests completed successfully!")
    else:
        print("❌ Tests failed!")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
