# Path Management Violations Report

## Executive Summary

After a comprehensive analysis of the backend codebase, I found several violations of the CLAUDE.md architecture rule: "NEVER use hardcoded absolute paths - Use config-driven paths from settings.data_directory". The violations are primarily in the form of:

1. Hardcoded directory names without using settings configuration
2. Manual path construction instead of using pathlib.Path or file_helpers
3. Direct path string concatenation
4. Inconsistent use of the configured base directories

## Key Findings

### 1. **RTSPCapture Service** (`backend/app/services/rtsp_capture_service.py`)

**Violations Found:**
- Line 25: `def __init__(self, base_data_dir: str = "/data"):`
  - **Issue**: Hardcoded default path "/data"
  - **Fix**: Should use `settings.data_directory` as default
  
- Lines 40-45: Manual path construction with hardcoded subdirectories
  ```python
  frames_dir = (
      self.base_data_dir
      / "cameras"  # Hardcoded subdirectory
      / f"camera-{camera_id}"
      / f"timelapse-{timelapse_id}"
      / "frames"
  )
  ```
  - **Fix**: Should use `settings.images_directory` and proper path helpers

- Lines 53-59: Hardcoded directory structure
  ```python
  directories = {
      "images": base_dir / "images" / today,
      "thumbnails": base_dir / "thumbnails" / today,
      "small": base_dir / "small" / today,
  }
  ```
  - **Fix**: Should use settings properties like `settings.thumbnails_directory`

### 2. **Thumbnail Utils** (`backend/app/utils/thumbnail_utils.py`)

**Violations Found:**
- Lines 96-109: Hardcoded path construction
  ```python
  directories = {
      "thumbnails": Path(f"cameras/camera-{camera_id}/thumbnails/{today}")
  }
  ```
  - **Issue**: Direct path construction without using base directory
  - **Fix**: Should use `Path(settings.thumbnails_directory) / f"camera-{camera_id}" / today`

### 3. **Image Service** (`backend/app/services/image_service.py`)

**Status**: ✅ Clean - Properly uses database operations and file_helpers

### 4. **Video Service** (`backend/app/services/video_service.py`)

**Status**: ✅ Clean - Properly imports and uses file_helpers for path operations

### 5. **Worker** (`backend/worker.py`)

**Status**: ✅ Clean - Uses composition-based services and proper configuration

### 6. **Camera Model** (`backend/app/models/camera_model.py`)

**Status**: ✅ Clean - No hardcoded paths, only model definitions

## Current Path Configuration Status

The `backend/app/config.py` file properly implements path configuration:

✅ **Strengths:**
- Configurable `data_directory` with environment variable override
- Proper Path object usage
- Helper methods for path conversion (`get_full_file_path`, `get_relative_path`)
- Subdirectory properties (images, videos, thumbnails, logs)
- Automatic directory creation on startup

✅ **File Helpers Available:**
The `backend/app/utils/file_helpers.py` provides excellent utilities:
- `validate_file_path()` - Security-aware path validation
- `get_relative_path()` - Convert absolute to relative paths
- `ensure_directory_exists()` - Safe directory creation
- Path traversal protection
- Cross-platform compatibility with pathlib

## Recommendations

### Immediate Actions Required:

1. **Fix RTSPCapture Service**
   ```python
   # Change from:
   def __init__(self, base_data_dir: str = "/data"):
   
   # To:
   def __init__(self, base_data_dir: Optional[str] = None):
       self.base_data_dir = Path(base_data_dir or settings.data_directory)
   ```

2. **Update Directory Creation Methods**
   ```python
   # Use settings for all subdirectories:
   frames_dir = Path(settings.images_directory) / f"camera-{camera_id}" / f"timelapse-{timelapse_id}" / "frames"
   
   # Or better, use file_helpers:
   from ..utils.file_helpers import ensure_directory_exists
   frames_dir = ensure_directory_exists(
       f"{settings.images_directory}/camera-{camera_id}/timelapse-{timelapse_id}/frames"
   )
   ```

3. **Fix Thumbnail Utils**
   ```python
   # Instead of hardcoded paths:
   thumbnail_path = Path(settings.thumbnails_directory) / f"camera-{camera_id}" / today / filename
   
   # Use file_helpers for relative paths:
   relative_path = get_relative_path(thumbnail_path, settings.data_directory)
   ```

### Best Practices to Enforce:

1. **Never hardcode directory names** - Always use settings properties
2. **Use pathlib.Path exclusively** - No string concatenation for paths
3. **Leverage file_helpers.py** - Use existing utilities for all path operations
4. **Store relative paths in database** - Use `get_relative_path()` before storage
5. **Validate paths on retrieval** - Use `validate_file_path()` when reading files

### Additional Improvements Needed:

1. **Create a centralized path manager** service that encapsulates all path operations
2. **Add unit tests** for path operations to prevent regressions
3. **Add pre-commit hooks** to check for hardcoded paths
4. **Document path conventions** in developer guidelines

## Compliance Score

**Current Compliance: 70%**
- ✅ Config properly set up with path management
- ✅ File helpers available and comprehensive
- ✅ Most services use proper abstractions
- ❌ Some services still have hardcoded paths
- ❌ Inconsistent usage of path utilities

## Next Steps

1. Refactor `rtsp_capture_service.py` to use settings and file_helpers
2. Update `thumbnail_utils.py` to use configured base directories
3. Audit all database operations to ensure relative paths are stored
4. Add integration tests for path operations
5. Create developer documentation on proper path handling

This report identifies the main violations and provides clear remediation steps to achieve full compliance with the AI-CONTEXT path management requirements.