# Overlay Pipeline

## Overview

The Overlay Pipeline is a comprehensive system for generating dynamic overlays
on timelapse images. It supports text-based overlays (timestamps, weather, frame
numbers), image overlays (watermarks, logos), and custom content with flexible
positioning and styling.

**Key Features:**

- 🎨 **Built-in Templates**: 3+ pre-configured overlay templates for common use
  cases
- 🐳 **Docker Ready**: Automatic template seeding during container deployment
- 🔧 **Flexible Configuration**: Grid-based positioning with global and per-item
  styling
- 🌤️ **Weather Integration**: Live weather data overlays
- 📊 **Performance Optimized**: Caching and background job processing

## Template System

### Built-in Templates

The system includes pre-configured templates that are automatically seeded
during fresh database deployments:

1. **Basic Timestamp** - Simple date/time overlay for general use
2. **Weather & Time** - Weather conditions with timestamp for outdoor timelapses
3. **Complete Information** - Comprehensive overlay using all four corners

### Template Management

```bash
# Check template status
python3 init_templates.py --status

# Initialize templates manually
python3 init_templates.py

# Docker deployment (automatic)
# Templates are seeded during fresh database initialization
```

**Template Location**: `app/database/templates/`

- `basic_timestamp.json`
- `weather_info.json`
- `complete_overlay.json`
- `README.md` (documentation)

## Externally Associated Files

### Core Backend Files

- backend/app/database/overlay_job_operations.py
- backend/app/database/overlay_operations.py
- backend/app/models/overlay_model.py
- backend/app/utils/file_helpers.py
- backend/app/utils/time_utils.py
- backend/app/utils/temp_file_manager.py

### Template System Files

- backend/app/database/template_initializer.py
- backend/app/database/templates/\*.json
- backend/init_templates.py
- backend/app/database/migrations.py (integration)

### Documentation

- \_system-guides/TIMELAPSE_OVERLAY_SYSTEM.md
- backend/app/database/templates/README.md

### Pytests

- backend/tests/unit/database/test_overlay_operations.py
- backend/tests/unit/database/test_overlay_job_operations.py
- backend/tests/unit/services/test_overlay_integration_service.py
- backend/tests/integration/test_overlay_pipeline_integration.py
- backend/tests/unit/database/test_overlay_job_operations.py

### Frontend

- src/hooks/use-overlay-presets.ts
- src/lib/overlay-presets-data.ts
- src/components/timelapse-creation/slides/overlays-slide.tsx
- src/components/edit-timelapse-modal/overlays-tab.tsx
- src/app/overlays/\*

## Frontend JSON Payload Example

The frontend sends overlay configuration as an array of overlay items:

```json
{
  "globalSettings": {
    "opacity": 100,
    "font": "Arial",
    "xMargin": 20,
    "yMargin": 20,
    "backgroundColor": "#000000",
    "backgroundOpacity": 50,
    "fillColor": "#FFFFFF",
    "dropShadow": 2,
    "preset": "weather-timestamp"
  },
  "overlayItems": [
    {
      "type": "date_time",
      "position": "topLeft",
      "enabled": true,
      "settings": {
        "dateFormat": "YYYY-MM-DD HH:mm:ss",
        "textSize": 16,
        "enableBackground": true
      }
    },
    {
      "type": "temperature",
      "position": "topRight",
      "enabled": true,
      "settings": {
        "unit": "F",
        "display": "temp_only",
        "textSize": 14,
        "enableBackground": false
      }
    },
    {
      "type": "frame_number",
      "position": "bottomLeft",
      "enabled": true,
      "settings": {
        "leadingZeros": true,
        "hidePrefix": false,
        "textSize": 12,
        "enableBackground": true
      }
    },
    {
      "type": "custom_text",
      "position": "bottomCenter",
      "enabled": true,
      "settings": {
        "customText": "My Garden Timelapse",
        "textSize": 18,
        "enableBackground": false
      }
    },
    {
      "type": "watermark",
      "position": "bottomRight",
      "enabled": true,
      "settings": {
        "imageUrl": "/assets/logo.png",
        "scale": 80,
        "enableBackground": false
      }
    }
  ]
}
```

## Overlay Modules

### Text-Based Modules

- **date** - Current date only
- **date_time** - Combined date and time with custom formatting
- **time** - Current time only
- **frame_number** - Sequential frame number in timelapse
- **day_number** - Day count since timelapse started
- **custom_text** - User-defined static text
- **timelapse_name** - Name of the current timelapse

### Weather Modules

- **temperature** - Current temperature reading
- **weather_conditions** - Weather description (sunny, cloudy, etc.)
- **weather_temp_conditions** - Combined temperature and conditions

### Image Modules

- **watermark** - Custom image overlay (logos, watermarks, etc.)

## Docker Deployment

### Automatic Template Seeding

For Docker deployments, overlay templates are automatically initialized during
fresh database setup:

1. **Database Detection**: System detects fresh database (no Alembic history)
2. **Schema Creation**: Creates database schema from SQL file
3. **Template Initialization**: Automatically seeds built-in overlay templates
4. **Alembic Stamping**: Marks database as current revision

```python
# Fresh database initialization includes templates
result = initialize_database()
# Returns: "Fresh database initialized successfully with 3 overlay templates"
```

### Template Configuration Format

Templates use the unified overlay format with overlay_items array:

```json
{
  "name": "Template Name",
  "description": "Template description",
  "overlay_config": {
    "overlay_items": [
      {
        "id": "timestamp_1",
        "type": "date_time",
        "position": "bottomLeft",
        "enabled": true,
        "settings": {
          "textSize": 18,
          "textColor": "#FFFFFF",
          "backgroundOpacity": 60,
          "dateFormat": "MM/dd/yyyy HH:mm"
        }
      }
    ],
    "global_settings": {
      "opacity": 100,
      "font": "Arial",
      "x_margin": 25,
      "y_margin": 25
    }
  },
  "is_builtin": true
}
```

## Process Flow

### 1. Request Entry

**Responsible**: `OverlayPipeline.generate_overlay_for_image()`

- Receives image_id and optional force_regenerate flag
- Entry point from scheduler, manual requests, or job queue

### 2. Configuration Loading

**Responsible**: `OverlaySettingsResolver.get_effective_configuration()`

- Load timelapse overlay configuration from database
- Load preset configuration if specified
- Merge inheritance chain: defaults → preset → timelapse overrides

### 3. Data Transformation

**Responsible**: _[UNIFIED FORMAT COMPLETED]_

- Backend now uses unified overlay_items array format matching frontend
- No transformation needed - frontend and backend use consistent data structure
- Unified OverlayConfiguration model handles all overlay settings consistently

### 4. Business Logic Coordination

**Responsible**: `OverlayIntegrationService._render_overlay_for_image()`

- Validate overlay configuration completeness
- Load base image from filesystem using image_id
- Coordinate rendering process and error handling

### 5. Content Generation

**Responsible**: `OverlayRenderer._get_overlay_content()` _[CURRENT MONOLITHIC
APPROACH]_

- Large if-elif chain handles all overlay module types
- Generate text content for date/time/weather/sequence modules
- Load and scale image assets for watermark modules
- Apply module-specific formatting and calculations

### 6. Image Composition

**Responsible**: `OverlayRenderer` PIL/Pillow operations

- Position overlays on 9-grid system (topLeft, topCenter, etc.)
- Apply global styling (font, margins, opacity)
- Apply per-item styling (text size, colors, backgrounds)
- Composite all elements onto base image

### 7. File Output

**Responsible**: `OverlayIntegrationService`

- Save final composited image to filesystem
- Return success/failure status with error details
- Update database records if needed

## Template System Architecture

### Database Integration

- **Template Storage**: Built-in templates stored in `overlay_presets` table
  with `is_builtin=true`
- **User Presets**: User-created presets stored with `is_builtin=false`
- **Template Seeding**: Automatic during fresh database initialization
- **Duplicate Prevention**: Templates only inserted if name doesn't exist

### Template Lifecycle

1. **Development**: JSON templates created in `app/database/templates/`
2. **Validation**: Template structure validated during loading
3. **Deployment**: Auto-seeded during Docker container startup
4. **Runtime**: Available as selectable presets in UI
5. **Inheritance**: Templates can be customized per-timelapse

### CLI Management

```bash
# Template status and management
python3 init_templates.py --status        # Check template status
python3 init_templates.py                 # Initialize templates
python3 init_templates.py --json          # JSON output
python3 test_docker_templates.py          # Test Docker readiness
```

## Current Architecture Status

### ✅ Completed Features

1. **Template System**: Built-in templates with Docker deployment
2. **Database Operations**: Full CRUD for presets and configurations
3. **Grid Positioning**: 9-position overlay system (topLeft, center, etc.)
4. **Content Generation**: Support for all major overlay types
5. **Error Handling**: Graceful fallbacks and validation

### 🔄 Ongoing Issues

1. **Monolithic Content Generation**: Single large if-elif chain instead of
   modular generators
2. **Performance**: Limited caching of static overlay elements
3. **Frontend Legacy Patterns**: Frontend still contains legacy overlayPositions
   format in some components

## Future Improvements

- Individual module generators for each overlay type
- Static overlay template caching for performance
- Frontend-backend data transformation adapter
- Enhanced property support and validation
- Template versioning and migration system
- Dynamic template loading from external sources
