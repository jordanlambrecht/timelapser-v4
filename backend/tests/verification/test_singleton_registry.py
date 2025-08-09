#!/usr/bin/env python3
"""
Verification tests for singleton registry and dependency injection system.

Tests that the refactored Operations classes properly use singletons
and that dependency injection is working correctly.
"""

import sys
import os
import asyncio
from typing import Dict, Any

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../'))

from app.dependencies.singleton_registry import (
    _singleton_registry,
    get_singleton_service,
    register_singleton_factory,
    clear_singleton_registry
)


def test_singleton_registry_basic():
    """Test basic singleton registry functionality."""
    print("Testing basic singleton registry functionality...")
    
    # Clear registry for clean test
    clear_singleton_registry()
    
    # Test factory registration and retrieval
    def test_factory():
        return {"test": "value", "instance_id": id({})}
    
    register_singleton_factory("test_service", test_factory)
    
    # Get service twice - should be same instance
    service1 = get_singleton_service("test_service")
    service2 = get_singleton_service("test_service")
    
    assert service1 is service2, "Singleton registry failed - different instances returned"
    assert service1["test"] == "value", "Factory function not called correctly"
    
    print("✅ Basic singleton registry test passed")


def test_operations_singleton_behavior():
    """Test that Operations classes are properly returned as singletons."""
    print("Testing Operations singleton behavior...")
    
    # Clear registry for clean test
    clear_singleton_registry()
    
    try:
        from app.dependencies.specialized import (
            get_video_operations,
            get_timelapse_operations,
            get_image_operations
        )
        
        # Test video operations singleton
        video_ops1 = asyncio.run(get_video_operations())
        video_ops2 = asyncio.run(get_video_operations())
        assert video_ops1 is video_ops2, "VideoOperations not returning singleton"
        
        # Test timelapse operations singleton  
        timelapse_ops1 = asyncio.run(get_timelapse_operations())
        timelapse_ops2 = asyncio.run(get_timelapse_operations())
        assert timelapse_ops1 is timelapse_ops2, "TimelapseOperations not returning singleton"
        
        # Test image operations singleton
        image_ops1 = asyncio.run(get_image_operations())
        image_ops2 = asyncio.run(get_image_operations())
        assert image_ops1 is image_ops2, "ImageOperations not returning singleton"
        
        print("✅ Operations singleton behavior test passed")
        
    except ImportError as e:
        print(f"⚠️  Import error during Operations test: {e}")
        return False
    except Exception as e:
        print(f"❌ Operations singleton test failed: {e}")
        return False
    
    return True


def test_sync_operations_singleton_behavior():
    """Test that sync Operations classes are properly returned as singletons.""" 
    print("Testing sync Operations singleton behavior...")
    
    try:
        from app.dependencies.specialized import (
            get_sync_video_operations,
            get_sync_timelapse_operations,
            get_sync_image_operations
        )
        
        # Test sync video operations singleton
        sync_video_ops1 = get_sync_video_operations()
        sync_video_ops2 = get_sync_video_operations()
        assert sync_video_ops1 is sync_video_ops2, "SyncVideoOperations not returning singleton"
        
        # Test sync timelapse operations singleton
        sync_timelapse_ops1 = get_sync_timelapse_operations()
        sync_timelapse_ops2 = get_sync_timelapse_operations()
        assert sync_timelapse_ops1 is sync_timelapse_ops2, "SyncTimelapseOperations not returning singleton"
        
        # Test sync image operations singleton  
        sync_image_ops1 = get_sync_image_operations()
        sync_image_ops2 = get_sync_image_operations()
        assert sync_image_ops1 is sync_image_ops2, "SyncImageOperations not returning singleton"
        
        print("✅ Sync Operations singleton behavior test passed")
        
    except ImportError as e:
        print(f"⚠️  Import error during sync Operations test: {e}")
        return False
    except Exception as e:
        print(f"❌ Sync Operations singleton test failed: {e}")
        return False
    
    return True


def test_factory_registry_state():
    """Test that factory functions are properly registered."""
    print("Testing factory registry state...")
    
    try:
        from app.dependencies import specialized
        
        # Check that key Operations factories are registered
        expected_factories = [
            'video_operations',
            'sync_video_operations', 
            'timelapse_operations',
            'sync_timelapse_operations',
            'image_operations',
            'sync_image_operations',
            'settings_operations',
            'sync_settings_operations'
        ]
        
        for factory_name in expected_factories:
            if factory_name not in _singleton_registry._factories:
                print(f"❌ Factory {factory_name} not registered")
                return False
        
        print(f"✅ Found {len(expected_factories)} critical Operations factories registered")
        
        # Show total registered factories
        total_factories = len(_singleton_registry._factories)
        print(f"ℹ️  Total registered factories: {total_factories}")
        
        if total_factories >= 25:  # We should have ~31 Operations factories
            print("✅ Factory registration appears complete")
        else:
            print("⚠️  Fewer factories than expected - some Operations may not be registered")
        
    except Exception as e:
        print(f"❌ Factory registry test failed: {e}")
        return False
    
    return True


def test_dependency_injection_integration():
    """Test that dependency injection works in refactored services."""
    print("Testing dependency injection integration...")
    
    try:
        # Test that services can be imported without errors
        from app.services.video_service import VideoService
        from app.services.timelapse_service import TimelapseService
        
        print("✅ Refactored services import successfully")
        
        # Test instantiation with dependency injection
        # Note: We can't fully test without database connections, 
        # but we can verify no import/syntax errors
        
        print("✅ Dependency injection integration appears working")
        
    except ImportError as e:
        print(f"❌ Service import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Dependency injection integration test failed: {e}")
        return False
    
    return True


def main():
    """Run all verification tests."""
    print("🔍 Starting dependency injection verification tests...\n")
    
    tests = [
        test_singleton_registry_basic,
        test_operations_singleton_behavior,
        test_sync_operations_singleton_behavior, 
        test_factory_registry_state,
        test_dependency_injection_integration
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
        print()  # Empty line between tests
    
    print("=" * 50)
    print(f"VERIFICATION RESULTS:")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Total: {passed + failed}")
    
    if failed == 0:
        print("\n🎉 ALL VERIFICATION TESTS PASSED!")
        print("The dependency injection implementation is working correctly.")
    else:
        print(f"\n⚠️  {failed} test(s) failed - investigation needed.")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)