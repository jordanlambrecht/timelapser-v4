# CAMERA_CROP_ROTATION_SYSTEM.md

## Overview

The Camera Crop & Rotation System handles physical camera adjustments at the
camera domain level, ensuring all captured images are properly oriented and
framed before any timelapse processing occurs. This system uses OpenCV for
immediate post-capture processing and applies transformations to every image
from the camera.

**Core Principle**: Camera settings are about correcting physical mounting
issues and framing, not creative choices. These settings affect ALL timelapses
from this camera.

**Architecture Approach:**

- **OpenCV Processing**: Crop and rotation applied immediately after RTSP
  capture
- **Camera Domain**: Settings stored per-camera, not per-timelapse
- **Universal Application**: All timelapses inherit camera's crop/rotation
  settings
- **Performance Optimized**: Process once at capture, not during video
  generation

**Use Cases:**

- **Rotation**: Camera mounted upside-down or at 90° angle
- **Cropping**: Remove unwanted objects (fence, building edge, etc.)
- **Aspect Ratio**: Set consistent aspect ratio for all timelapses from this
  camera
- **Framing**: Focus on specific area of camera's field of view

## User Interface Design

### Access Pattern

**Location**: `/cameras/[id]` page **Trigger**: Settings cog icon (⚙️) in camera
header/toolbar **Flow**: Cog → Context Menu → "Adjust Cropping/Rotation" → Modal

### Context Menu

```
Settings Cog (⚙️) →
├── Adjust Cropping/Rotation
├── Camera Configuration
├── Connection Settings
├── Health Check Settings
└── Delete Camera
```

### Crop & Rotation Modal

**Modal Structure:**

```
┌─────────────────────────────────────────────┐
│ Camera Settings: [Camera Name]               │
│                                          [X] │
├─────────────────────────────────────────────┤
│                                             │
│  ┌─── Image Preview ───┐  ┌─── Controls ─┐  │
│  │                     │  │              │  │
│  │     Test Shot       │  │   Rotation   │  │
│  │   or Latest Image   │  │   ○ 0°       │  │
│  │    or Placeholder   │  │   ○ 90°      │  │
│  │                     │  │   ○ 180°     │  │
│  │    [Crop Overlay]   │  │   ○ 270°     │  │
│  │                     │  │              │  │
│  └─────────────────────┘  │   Aspect     │  │
│                           │   Ratio      │  │
│  ┌─── Crop Controls ───┐  │   ○ Original │  │
│  │ X: [    ] Y: [    ] │  │   ○ 16:9     │  │
│  │ W: [    ] H: [    ] │  │   ○ 9:16     │  │
│  │                     │  │   ○ 4:3      │  │
│  │ [Reset] [Center]    │  │   ○ 1:1      │  │
│  └─────────────────────┘  │   ○ Custom   │  │
│                           │              │  │
│                           │ [Test Shot]  │  │
│                           └──────────────┘  │
├─────────────────────────────────────────────┤
│                    [Cancel] [Apply Changes] │
└─────────────────────────────────────────────┘
```

### UI Components Breakdown

**Image Preview Area:**

- **Live Preview**: Show camera feed with current settings applied
- **Crop Overlay**: Interactive crop box with resize handles
- **Grid Lines**: Rule of thirds grid for composition guidance
- **Zoom Controls**: Zoom in/out for precise crop adjustment

**Rotation Controls:**

- **Radio Buttons**: 0°, 90°, 180°, 270° options
- **Real-time Update**: Preview rotates immediately when selected
- **Common Use Cases**: Handle upside-down or sideways mounted cameras

**Aspect Ratio Controls:**

- **Preset Options**: Original, 16:9, 9:16, 4:3, 1:1, Custom
- **Constraint Behavior**: Crop box locks to selected aspect ratio
- **Custom Input**: Width × Height input fields for custom ratios

**Crop Controls:**

- **Coordinate Inputs**: X, Y position and Width, Height dimensions
- **Interactive Handles**: Drag corners and edges to adjust crop area
- **Quick Actions**: Reset to full image, Center crop area
- **Real-time Values**: Inputs update as user drags crop box

**Test Shot Button:**

- **Fresh Capture**: Take new photo with current settings applied
- **Validation**: Ensure settings work correctly before applying
- **Preview Update**: Replace preview with test shot result

## Technical Implementation

### Frontend Architecture

**Component Structure:**

```
CameraCropRotationModal/
├── ImagePreviewCanvas
│   ├── LiveFeedDisplay
│   ├── CropOverlay
│   └── GridLines
├── RotationControls
│   └── RadioButtonGroup
├── AspectRatioSelector
│   ├── PresetButtons
│   └── CustomInputs
├── CropInputControls
│   ├── CoordinateInputs
│   └── QuickActions
└── ActionButtons
    ├── TestShotButton
    ├── CancelButton
    └── ApplyButton
```

**State Management:**

```typescript
interface CameraCropRotationSettings {
  rotation: 0 | 90 | 180 | 270
  aspectRatio: {
    type: "original" | "16:9" | "9:16" | "4:3" | "1:1" | "custom"
    customWidth?: number
    customHeight?: number
  }
  cropArea: {
    x: number // Pixels from left
    y: number // Pixels from top
    width: number // Crop width in pixels
    height: number // Crop height in pixels
  }
  sourceResolution: {
    width: number // Original camera resolution
    height: number // Original camera resolution
  }
}

interface CameraSettingsModalState {
  isOpen: boolean
  settings: CameraCropRotationSettings
  previewImage: string | null
  isLoading: boolean
  hasUnsavedChanges: boolean
}
```

### Backend Architecture

**Database Schema Extensions:**

```sql
-- Add to cameras table
ALTER TABLE cameras ADD COLUMN crop_rotation_settings JSONB DEFAULT '{}';
ALTER TABLE cameras ADD COLUMN crop_rotation_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE cameras ADD COLUMN source_resolution JSONB DEFAULT '{}'; -- {"width": 1920, "height": 1080}

-- Performance index
CREATE INDEX idx_cameras_crop_rotation ON cameras USING GIN (crop_rotation_settings);
```

**Settings Storage Format:**

```json
{
  "rotation": 0,
  "aspectRatio": {
    "type": "16:9"
  },
  "cropArea": {
    "x": 100,
    "y": 50,
    "width": 1720,
    "height": 967
  },
  "sourceResolution": {
    "width": 1920,
    "height": 1080
  },
  "enabled": true,
  "updatedAt": "2025-01-10T14:30:00Z"
}
```

**Service Layer Integration:**

**`/app/services/camera_crop_service.py`**

```python
class CameraCropService:
    def __init__(self, db: SyncDatabase, camera_ops: SyncCameraOperations):
        self.db = db
        self.camera_ops = camera_ops

    def get_crop_settings(self, camera_id: int) -> Dict[str, Any]
    def update_crop_settings(self, camera_id: int, settings: Dict[str, Any]) -> bool
    def apply_crop_rotation(self, image: np.ndarray, settings: Dict[str, Any]) -> np.ndarray
    def get_effective_resolution(self, camera_id: int) -> Tuple[int, int]
    def capture_test_image(self, camera_id: int) -> str
```

**OpenCV Processing Integration:**

```python
def process_captured_image(self, image: np.ndarray, camera_id: int) -> np.ndarray:
    """Apply camera's crop and rotation settings to captured image."""
    settings = self.get_crop_settings(camera_id)

    if not settings.get('enabled', False):
        return image

    # Apply rotation first
    rotation = settings.get('rotation', 0)
    if rotation != 0:
        image = self.rotate_image(image, rotation)

    # Apply cropping
    crop_area = settings.get('cropArea')
    if crop_area:
        x, y = crop_area['x'], crop_area['y']
        w, h = crop_area['width'], crop_area['height']
        image = image[y:y+h, x:x+w]

    return image
```

### API Endpoints

**Router: `/app/routers/camera_crop_routers.py`**

```python
@router.get("/cameras/{camera_id}/crop-settings")
async def get_camera_crop_settings(camera_id: int)

@router.put("/cameras/{camera_id}/crop-settings")
async def update_camera_crop_settings(camera_id: int, settings: CameraCropSettingsModel)

@router.post("/cameras/{camera_id}/test-crop")
async def capture_test_image(camera_id: int, settings: CameraCropSettingsModel)

@router.get("/cameras/{camera_id}/live-preview")
async def get_live_preview_image(camera_id: int)
```

### Integration Points

**ImageCaptureService Integration:**

```python
# In ImageCaptureService.capture_and_process_image()
def capture_and_process_image(self, camera_id: int):
    # 1. Capture from RTSP
    raw_image = self.rtsp_capture(camera_id)

    # 2. Apply camera crop/rotation settings
    processed_image = self.camera_crop_service.apply_crop_rotation(
        raw_image, camera_id
    )

    # 3. Continue with existing pipeline (corruption detection, etc.)
    return self.continue_processing(processed_image, camera_id)
```

**File Structure Impact:**

```
data/cameras/camera-{id}/
├── frames/              # NOW: Cropped/rotated final images
├── overlays/            # Overlays applied to cropped images
├── thumbnails/          # Generated from cropped images
├── smalls/             # Generated from cropped images
└── videos/             # Generated from cropped images
```

## User Experience Flow

### Setup Flow

1. **Access**: User clicks settings cog on camera page
2. **Context Menu**: Selects "Adjust Cropping/Rotation"
3. **Modal Opens**: Shows current camera feed/latest image
4. **Configure**: User adjusts rotation, aspect ratio, and crop area
5. **Test**: Click "Test Shot" to capture with new settings
6. **Validate**: Preview updates with test shot result
7. **Apply**: User confirms and applies settings
8. **Effect**: All future captures use new settings

### Real-World Scenarios

**Scenario 1: Upside-Down Camera**

- User selects 180° rotation
- Preview immediately shows corrected orientation
- Test shot confirms correct rotation
- Apply settings - all future images right-side up

**Scenario 2: Remove Fence from View**

- User drags crop box to exclude fence area
- Selects 16:9 aspect ratio for cinematic look
- Test shot shows clean frame without fence
- Apply settings - all timelapses now fence-free

**Scenario 3: Portrait Orientation**

- Camera mounted sideways for tall subject
- User selects 90° rotation and 9:16 aspect ratio
- Crop area adjusted to frame subject properly
- Apply settings - perfect for mobile/social media content

## Implementation Considerations

### Performance Optimization

- **OpenCV Processing**: Optimized crop/rotate operations
- **Cache Settings**: Camera settings cached to avoid repeated DB queries
- **Preview Generation**: Efficient preview updates during configuration
- **Test Shots**: Temporary images for validation (not stored permanently)

### Error Handling

- **Invalid Coordinates**: Validate crop area stays within image bounds
- **Aspect Ratio Conflicts**: Ensure crop dimensions match selected aspect ratio
- **Camera Offline**: Graceful handling when camera unavailable for test shots
- **Settings Validation**: Ensure rotation and crop values are within valid
  ranges

### Backward Compatibility

- **Existing Images**: Unaffected (already captured)
- **Default Behavior**: Cameras without settings continue normal operation
- **Migration Path**: Easy to enable/disable crop/rotation per camera

---

## GPT Implementation Prompt

```
I need you to implement a Camera Crop & Rotation System for a timelapse application built with Next.js 15 (App Router) and FastAPI backend.

SYSTEM OVERVIEW:
Create a camera-level crop and rotation system that processes images immediately after RTSP capture using OpenCV. This is NOT a timelapse feature - it's a camera configuration that affects ALL images captured from that camera.

CORE REQUIREMENTS:

1. UI IMPLEMENTATION:
   - Add settings cog (⚙️) to camera detail page (/cameras/[id])
   - Create context menu with "Adjust Cropping/Rotation" option
   - Build modal with live preview, rotation controls, aspect ratio selection, and crop area adjustment
   - Include interactive crop box with drag handles and coordinate inputs
   - Add "Test Shot" button to capture preview with current settings

2. BACKEND IMPLEMENTATION:
   - Extend cameras table with crop_rotation_settings JSONB column
   - Create CameraCropService for settings management and OpenCV processing
   - Add API endpoints for getting/setting crop settings and capturing test images
   - Integrate with existing ImageCaptureService to apply settings after RTSP capture

3. TECHNICAL SPECIFICATIONS:
   - Use OpenCV for rotation (0°, 90°, 180°, 270°) and cropping operations
   - Support aspect ratios: Original, 16:9, 9:16, 4:3, 1:1, Custom
   - Store settings as JSONB: {rotation, aspectRatio, cropArea, sourceResolution}
   - Apply transformations immediately after capture, before any other processing

4. INTEGRATION POINTS:
   - Hook into existing ImageCaptureService.capture_and_process_image()
   - Ensure thumbnail generation, overlay system, and video generation work with processed images
   - Maintain compatibility with existing corruption detection and health monitoring

5. UX REQUIREMENTS:
   - Real-time preview updates as user adjusts settings
   - Interactive crop box with visual feedback
   - Test shot functionality to validate settings before applying
   - Clear indication of unsaved changes
   - Intuitive controls for common camera mounting scenarios

EXISTING CODEBASE CONTEXT:
- FastAPI backend with composition-pattern database operations
- PostgreSQL with JSONB support and psycopg3
- Next.js frontend with TypeScript and Tailwind CSS
- Existing camera service architecture with dependency injection
- OpenCV already available for image processing
- File structure: data/cameras/camera-{id}/frames/ for processed images

KEY FILES TO CREATE/MODIFY:
- Frontend: Camera detail page, crop rotation modal component
- Backend: CameraCropService, camera crop router, database migration
- Integration: ImageCaptureService modification for applying settings

IMPORTANT: This system processes images at capture time, not during video generation. The goal is "setup once, use forever" - configure camera mounting corrections that apply to all timelapses from that camera.

Please implement this system following the established patterns in the codebase, with proper error handling, TypeScript types, and responsive UI design.
```

This system guide provides a complete foundation for implementing camera-level
crop and rotation functionality that operates independently from the overlay
system, ensuring proper domain separation and optimal performance.
