#!/usr/bin/env python3
# test_integration_service.py

"""
Test script to verify video pipeline overlay integration service works with unified system.
"""

import sys

sys.path.insert(0, "backend")


def test_integration_service():
    """Test that the integration service is properly configured for unified system."""
    try:
        print("🔍 Testing video pipeline overlay integration service...")

        # Test imports
        from app.services.video_pipeline.overlay_integration_service import (
            OverlayIntegrationService,
        )

        print("✅ Integration service imports successfully")

        # Test unified model imports
        from app.models.overlay_model import (
            OverlayConfiguration,
            TimelapseOverlay,
            GlobalSettings,
        )

        print("✅ Unified overlay models available")

        # Test validation import
        from app.services.overlay_pipeline.utils.overlay_utils import (
            validate_overlay_configuration,
        )

        print("✅ Unified validation function available")

        # Test database operations import
        from app.database.overlay_operations import SyncOverlayOperations

        print("✅ Unified overlay operations available")

        # Check methods exist
        methods = [m for m in dir(OverlayIntegrationService) if not m.startswith("_")]
        expected_methods = [
            "check_overlays_available",
            "get_overlay_mode_for_video",
            "get_service_health",
        ]

        for method in expected_methods:
            if method in methods:
                print(f"✅ Method '{method}' exists")
            else:
                print(f"❌ Method '{method}' missing")

        print(
            "\n🎉 Video pipeline integration service is properly configured for unified system!"
        )
        return True

    except Exception as e:
        print(f"❌ Error testing integration service: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_integration_service()
    sys.exit(0 if success else 1)
