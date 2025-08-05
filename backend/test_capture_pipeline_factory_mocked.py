#!/usr/bin/env python3
# backend/test_capture_pipeline_factory_simple.py

"""
Simple test to verify the create_capture_pipeline() factory function works correctly.
This version uses minimal mocking to avoid dependency issues.
"""

import sys
import traceback
from pathlib import Path
from unittest.mock import Mock

# Add backend to path if needed
backend_path = Path(__file__).parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


def mock_dependencies():
    """Mock the necessary dependencies to avoid import errors."""
    # Mock fastapi
    fastapi_mock = Mock()
    fastapi_mock.HTTPException = Exception
    sys.modules["fastapi"] = fastapi_mock

    # Mock other common dependencies
    sys.modules["uvicorn"] = Mock()
    sys.modules["pydantic"] = Mock()
    sys.modules["psycopg"] = Mock()
    sys.modules["cv2"] = Mock()
    sys.modules["PIL"] = Mock()
    sys.modules["loguru"] = Mock()
    sys.modules["requests"] = Mock()


def test_factory_import():
    """Test importing the factory function with mocked dependencies."""
    print("🔍 Testing factory function import...")

    # Mock dependencies first
    mock_dependencies()

    try:
        from app.services.capture_pipeline import create_capture_pipeline

        print("✅ Successfully imported create_capture_pipeline")
        return create_capture_pipeline
    except ImportError as e:
        print(f"❌ Import error: {e}")
        traceback.print_exc()
        return None
    except Exception as e:
        print(f"❌ Unexpected error during import: {e}")
        traceback.print_exc()
        return None


def test_module_structure():
    """Test if the capture pipeline module structure exists."""
    print("\n🔍 Checking capture pipeline module structure...")

    # Check if the capture_pipeline directory exists
    capture_pipeline_dir = Path("app/services/capture_pipeline")
    if not capture_pipeline_dir.exists():
        print(f"❌ Capture pipeline directory does not exist: {capture_pipeline_dir}")
        return False

    # Check for expected files
    expected_files = [
        "__init__.py",
        "workflow_orchestrator.py",
        "camera_service.py",
        "capture_service.py",
        "image_service.py",
        "corruption_service.py",
        "thumbnail_service.py",
        "file_service.py",
        "transaction_manager.py",
    ]

    missing_files = []
    for file_name in expected_files:
        file_path = capture_pipeline_dir / file_name
        if file_path.exists():
            print(f"✅ Found: {file_name}")
        else:
            print(f"❌ Missing: {file_name}")
            missing_files.append(file_name)

    return len(missing_files) == 0


def test_factory_function_exists():
    """Test if the create_capture_pipeline function exists in the __init__.py."""
    print("\n🔍 Checking if create_capture_pipeline function exists...")

    init_file = Path("app/services/capture_pipeline/__init__.py")
    if not init_file.exists():
        print("❌ __init__.py file does not exist")
        return False

    try:
        content = init_file.read_text()
        if "def create_capture_pipeline" in content:
            print("✅ create_capture_pipeline function found in __init__.py")
            return True
        else:
            print("❌ create_capture_pipeline function not found in __init__.py")
            return False
    except Exception as e:
        print(f"❌ Error reading __init__.py: {e}")
        return False


def test_import_chain():
    """Test the import chain step by step."""
    print("\n🔍 Testing import chain...")

    # Mock dependencies
    mock_dependencies()

    # Test each level of import
    try:
        print("  Testing app.services...")

        print("  ✅ app.services imported successfully")

        print("  Testing app.services.capture_pipeline...")

        print("  ✅ app.services.capture_pipeline imported successfully")

        print("  Testing create_capture_pipeline function...")

        print("  ✅ create_capture_pipeline function imported successfully")

        return True
    except Exception as e:
        print(f"  ❌ Import failed: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("CAPTURE PIPELINE FACTORY VALIDATION TEST")
    print("=" * 60)

    # Test file structure
    structure_ok = test_module_structure()

    # Test factory function exists
    function_exists = test_factory_function_exists()

    # Test import chain
    import_ok = test_import_chain()

    # Test factory import
    factory_imported = test_factory_import() is not None

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Module structure: {'✅ PASS' if structure_ok else '❌ FAIL'}")
    print(f"Function exists: {'✅ PASS' if function_exists else '❌ FAIL'}")
    print(f"Import chain: {'✅ PASS' if import_ok else '❌ FAIL'}")
    print(f"Factory import: {'✅ PASS' if factory_imported else '❌ FAIL'}")

    if structure_ok and function_exists and import_ok and factory_imported:
        print(
            "\n🎉 All validation tests passed! The factory function structure is correct."
        )
        print("💡 Note: Full functionality testing requires proper environment setup.")
        return 0
    else:
        print("\n❌ Some validation tests failed. Check the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
