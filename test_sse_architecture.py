#!/usr/bin/env python3
"""
Test script to verify the new database-driven SSE architecture.
This tests the structure and patterns without requiring database connections.
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

def test_file_structure():
    """Test that all required files exist with proper structure"""
    print("🔍 Testing SSE architecture file structure...")
    
    required_files = [
        "backend/alembic/versions/018_add_sse_events_table.py",
        "backend/app/database/sse_events_operations.py", 
        "backend/app/routers/sse_routers.py",
        "src/app/api/events/route.ts"
    ]
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path}")
            return False
    
    return True

def test_migration_structure():
    """Test the SSE events table migration structure"""
    print("\n🗄️ Testing SSE events table migration...")
    
    migration_file = "backend/alembic/versions/018_add_sse_events_table.py"
    with open(migration_file, 'r') as f:
        content = f.read()
    
    required_elements = [
        'op.create_table(',
        '"sse_events"',
        'sa.Column("id"',
        'sa.Column("event_type"',
        'sa.Column("event_data"', 
        'sa.Column("created_at"',
        'sa.Column("processed_at"',
        'sa.Column("priority"',
        'sa.Column("source"',
        'idx_sse_events_unprocessed',
        'postgresql.JSONB'
    ]
    
    for element in required_elements:
        if element in content:
            print(f"✅ {element}")
        else:
            print(f"❌ {element}")
            return False
    
    return True

def test_operations_structure():
    """Test the SSE events operations classes"""
    print("\n🔧 Testing SSE events operations structure...")
    
    ops_file = "backend/app/database/sse_events_operations.py"
    with open(ops_file, 'r') as f:
        content = f.read()
    
    required_methods = [
        'class SSEEventsOperations:',
        'class SyncSSEEventsOperations:', 
        'async def create_event(',
        'async def get_pending_events(',
        'async def mark_events_processed(',
        'def create_image_captured_event(',
        'def create_camera_status_event(',
        'def create_timelapse_status_event('
    ]
    
    for method in required_methods:
        if method in content:
            print(f"✅ {method}")
        else:
            print(f"❌ {method}")
            return False
    
    return True

def test_router_structure():
    """Test the SSE router implementation"""
    print("\n🌐 Testing SSE router structure...")
    
    router_file = "backend/app/routers/sse_routers.py"
    with open(router_file, 'r') as f:
        content = f.read()
    
    required_elements = [
        '@router.get("/events")',
        'async def sse_event_stream(',
        'StreamingResponse(',
        'SSEEventsOperations(db)',
        'await sse_ops.get_pending_events(',
        'await sse_ops.mark_events_processed(',
        'media_type="text/event-stream"'
    ]
    
    for element in required_elements:
        if element in content:
            print(f"✅ {element}")
        else:
            print(f"❌ {element}")
            return False
    
    return True

def test_nextjs_proxy():
    """Test the Next.js streaming proxy"""
    print("\n🌉 Testing Next.js streaming proxy...")
    
    proxy_file = "src/app/api/events/route.ts"
    with open(proxy_file, 'r') as f:
        content = f.read()
    
    required_elements = [
        'export async function GET(',
        'fetch(backendSSEUrl',  # Updated to use fetch instead of EventSource
        'new ReadableStream(',
        'response.body.getReader()',  # Proper Node.js streaming
        'controller.enqueue',
        'new NextResponse(stream',
        '"Content-Type": "text/event-stream"'
    ]
    
    for element in required_elements:
        if element in content:
            print(f"✅ {element}")
        else:
            print(f"❌ {element}")
            return False
    
    return True

def test_old_sse_removal():
    """Test that old SSE implementation was removed"""
    print("\n🗑️ Testing old SSE implementation removal...")
    
    response_helpers = "backend/app/utils/response_helpers.py"
    with open(response_helpers, 'r') as f:
        content = f.read()
    
    removed_elements = [
        'class SSEEventManager:',
        'def broadcast_event(',
        'requests.post(',
        'import requests'
    ]
    
    for element in removed_elements:
        if element not in content:
            print(f"✅ Removed: {element}")
        else:
            print(f"❌ Still exists: {element}")
            return False
    
    # Should have replacement note
    if "NOTE: SSEEventManager class removed" in content:
        print("✅ Replacement documentation present")
    else:
        print("❌ Missing replacement documentation")
        return False
    
    return True

def test_service_updates():
    """Test that services were updated to use database SSE"""
    print("\n🔧 Testing service updates...")
    
    test_files = [
        "backend/app/services/camera_service.py",
        "backend/app/services/video_service.py", 
        "backend/app/services/settings_service.py"
    ]
    
    for service_file in test_files:
        if not os.path.exists(service_file):
            print(f"❌ File not found: {service_file}")
            continue
            
        with open(service_file, 'r') as f:
            content = f.read()
        
        # Should NOT contain old pattern
        if "SSEEventManager.broadcast_event" in content:
            print(f"❌ {service_file}: Still using old SSE pattern")
            return False
        
        # Should contain new pattern
        if "sse_ops.create_event" in content or "SSEEventsOperations" in content:
            print(f"✅ {service_file}: Updated to database SSE")
        else:
            print(f"❌ {service_file}: Missing database SSE integration")
            return False
    
    return True

def main():
    """Run all tests"""
    print("🚀 Testing Database-Driven SSE Architecture Implementation")
    print("=" * 60)
    
    tests = [
        test_file_structure,
        test_migration_structure, 
        test_operations_structure,
        test_router_structure,
        test_nextjs_proxy,
        test_old_sse_removal,
        test_service_updates
    ]
    
    all_passed = True
    for test in tests:
        if not test():
            all_passed = False
            print("❌ Test failed!")
            break
        print("✅ Test passed!")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Database-driven SSE architecture is ready!")
        print("\nNext steps:")
        print("1. Apply database migration: cd backend && alembic upgrade head")
        print("2. Start services: ./start-services.sh")
        print("3. Test real-time events in browser at http://localhost:3000")
        return 0
    else:
        print("💥 TESTS FAILED! Fix issues before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())