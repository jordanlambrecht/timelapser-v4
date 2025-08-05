#!/usr/bin/env python3
# backend/test_capture_pipeline_factory.py

"""
Simple test to verify the create_capture_pipeline() factory function works correctly.
This test checks for missing dependencies and import issues.
"""

import sys
import traceback
from pathlib import Path

# Add backend to path if needed
backend_path = Path(__file__).parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


def test_factory_import():
    """Test importing the factory function."""
    print("🔍 Testing factory function import...")
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


def test_factory_instantiation():
    """Test creating a pipeline instance."""
    print("\n🔍 Testing factory instantiation...")
    
    # First, try to import the factory
    factory = test_factory_import()
    if not factory:
        return None
    
    # Try to create a pipeline instance
    try:
        pipeline = factory()
        print("✅ Successfully created pipeline instance")
        return pipeline
    except ImportError as e:
        print(f"❌ Import error during instantiation: {e}")
        print("   Missing dependency or module")
        traceback.print_exc()
        return None
    except AttributeError as e:
        print(f"❌ Attribute error: {e}")
        print("   Likely missing class or method")
        traceback.print_exc()
        return None
    except Exception as e:
        print(f"❌ Unexpected error during instantiation: {e}")
        traceback.print_exc()
        return None


def test_instance_type():
    """Test if the returned instance is WorkflowOrchestratorService."""
    print("\n🔍 Testing instance type...")
    
    # Create pipeline
    pipeline = test_factory_instantiation()
    if not pipeline:
        return False
    
    # Check instance type
    try:
        from app.services.capture_pipeline.workflow_orchestrator import (
            WorkflowOrchestratorService,
        )
        
        if isinstance(pipeline, WorkflowOrchestratorService):
            print("✅ Pipeline is an instance of WorkflowOrchestratorService")
            return True
        else:
            print(f"❌ Pipeline is not WorkflowOrchestratorService, got: {type(pipeline)}")
            return False
    except ImportError as e:
        print(f"❌ Cannot import WorkflowOrchestratorService: {e}")
        traceback.print_exc()
        return False


def test_pipeline_attributes():
    """Test if the pipeline has expected attributes."""
    print("\n🔍 Testing pipeline attributes...")
    
    pipeline = test_factory_instantiation()
    if not pipeline:
        return
    
    # Check for expected attributes
    expected_attrs = [
        'process_capture',
        'camera_service',
        'capture_service',
        'image_service',
        'corruption_service',
        'thumbnail_service',
        'file_service',
        'transaction_manager'
    ]
    
    for attr in expected_attrs:
        if hasattr(pipeline, attr):
            print(f"✅ Has attribute: {attr}")
        else:
            print(f"❌ Missing attribute: {attr}")


def check_module_structure():
    """Check if the module structure exists."""
    print("\n🔍 Checking module structure...")
    
    modules_to_check = [
        'app.services.capture_pipeline',
        'app.services.capture_pipeline.workflow_orchestrator',
        'app.services.capture_pipeline.camera_service',
        'app.services.capture_pipeline.capture_service',
        'app.services.capture_pipeline.image_service',
        'app.services.capture_pipeline.corruption_service',
        'app.services.capture_pipeline.thumbnail_service',
        'app.services.capture_pipeline.file_service',
        'app.services.capture_pipeline.transaction_manager'
    ]
    
    for module_name in modules_to_check:
        try:
            __import__(module_name)
            print(f"✅ Module exists: {module_name}")
        except ImportError as e:
            print(f"❌ Module missing: {module_name} - {e}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("CAPTURE PIPELINE FACTORY TEST")
    print("=" * 60)
    
    # Check module structure first
    check_module_structure()
    
    # Test the factory
    print("\n" + "=" * 60)
    print("FACTORY FUNCTION TESTS")
    print("=" * 60)
    
    # Run tests
    factory_exists = test_factory_import() is not None
    instance_created = test_factory_instantiation() is not None
    correct_type = test_instance_type()
    
    if instance_created:
        test_pipeline_attributes()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Factory import: {'✅ PASS' if factory_exists else '❌ FAIL'}")
    print(f"Instance creation: {'✅ PASS' if instance_created else '❌ FAIL'}")
    print(f"Correct type: {'✅ PASS' if correct_type else '❌ FAIL'}")
    
    if factory_exists and instance_created and correct_type:
        print("\n🎉 All tests passed! The factory function works correctly.")
        return 0
    else:
        print("\n❌ Some tests failed. Check the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)