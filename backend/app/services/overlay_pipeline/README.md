# Overlay Pipeline

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
**Responsible**: *[TO BE IMPLEMENTED - Frontend Adapter]*
- Transform frontend overlayItems array to backend overlayPositions dict
- Convert frontend settings to backend OverlayItem properties
- Map position strings to GridPosition enum values

### 4. Business Logic Coordination
**Responsible**: `OverlayIntegrationService._render_overlay_for_image()`
- Validate overlay configuration completeness
- Load base image from filesystem using image_id
- Coordinate rendering process and error handling

### 5. Content Generation
**Responsible**: `OverlayRenderer._get_overlay_content()` *[CURRENT MONOLITHIC APPROACH]*
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

## Current Architecture Issues

1. **Data Structure Mismatch**: Frontend sends array, backend expects dict
2. **Monolithic Content Generation**: Single large if-elif chain instead of modular generators
3. **Missing Properties**: Backend doesn't support frontend properties (unit, display, leadingZeros, hidePrefix)
4. **Performance**: No caching of static overlay elements

## Future Improvements

- Individual module generators for each overlay type
- Static overlay template caching for performance
- Frontend-backend data transformation adapter
- Enhanced property support and validation