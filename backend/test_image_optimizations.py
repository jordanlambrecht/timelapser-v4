#!/usr/bin/env python3
"""
Test script to verify image operations optimizations.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database.image_operations import ImageQueryBuilder


def test_image_query_builder():
    """Test the ImageQueryBuilder implementations."""

    print("🧪 Testing ImageQueryBuilder...")

    # Test 1: Basic images query
    print("\n1. Testing build_images_query:")
    query, params = ImageQueryBuilder.build_images_query(
        timelapse_id=123, camera_id=456, limit=50, offset=100
    )
    print(f"   Query: {query}")
    print(f"   Params: {params}")
    expected_params = [123, 456, 50, 100]
    assert params == expected_params, f"Expected {expected_params}, got {params}"
    print("   ✅ Parameters match expected values")

    # Test 2: Images by IDs query
    print("\n2. Testing build_images_by_ids_query:")
    image_ids = [1, 2, 3, 4, 5]
    query, params = ImageQueryBuilder.build_images_by_ids_query(image_ids)
    print(f"   Query: {query}")
    print(f"   Params: {params}")
    assert params == image_ids, f"Expected {image_ids}, got {params}"
    print("   ✅ Parameters match expected values")

    # Test 3: Count query
    print("\n3. Testing build_count_query:")
    query, params = ImageQueryBuilder.build_count_query(
        timelapse_id=789, camera_id=101112
    )
    print(f"   Query: {query}")
    print(f"   Params: {params}")
    expected_params = [789, 101112]
    assert params == expected_params, f"Expected {expected_params}, got {params}"
    print("   ✅ Parameters match expected values")

    # Test 4: Empty ID list
    print("\n4. Testing empty image_ids list:")
    query, params = ImageQueryBuilder.build_images_by_ids_query([])
    print(f"   Query: {query}")
    print(f"   Params: {params}")
    assert params == [], "Expected empty params list"
    assert "WHERE FALSE" in query, "Expected WHERE FALSE for empty list"
    print("   ✅ Empty list handled correctly")

    print("\n🎉 All ImageQueryBuilder tests passed!")


def test_query_structure():
    """Test that generated queries have proper structure."""

    print("\n🔍 Testing query structure...")

    # Test with details
    query, params = ImageQueryBuilder.build_images_query(
        timelapse_id=1, include_details=True, limit=10
    )

    # Verify JOIN clauses are present when include_details=True
    assert "LEFT JOIN cameras c" in query, "Missing camera JOIN"
    assert "LEFT JOIN timelapses t" in query, "Missing timelapse JOIN"
    assert "camera_name" in query, "Missing camera_name field"
    assert "timelapse_status" in query, "Missing timelapse_status field"
    print("   ✅ Detailed query includes proper JOINs and fields")

    # Test without details
    query, params = ImageQueryBuilder.build_images_query(
        timelapse_id=1, include_details=False, limit=10
    )

    # Verify no JOIN clauses when include_details=False
    assert "LEFT JOIN" not in query, "Unexpected JOIN in simple query"
    assert "i.*" in query, "Missing basic fields selection"
    print("   ✅ Simple query excludes JOINs correctly")


if __name__ == "__main__":
    try:
        test_image_query_builder()
        test_query_structure()
        print("\n🚀 All tests passed! Image operations are properly optimized.")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
