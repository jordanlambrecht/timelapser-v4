# Overlay Template System

This directory contains JSON template files for built-in overlay presets that are automatically seeded into fresh database deployments.

## Template Files

### 1. `basic_timestamp.json`
- **Name**: Basic Timestamp
- **Description**: Simple date and time overlay in bottom-left corner with clean styling
- **Use Case**: General purpose timestamp overlay for most timelapses
- **Features**: Clean white text with semi-transparent background

### 2. `weather_info.json`
- **Name**: Weather & Time
- **Description**: Weather conditions with timestamp - perfect for outdoor timelapses
- **Use Case**: Outdoor timelapses where weather context is important
- **Features**: Weather temperature + conditions in top-left, timestamp in bottom-left

### 3. `complete_overlay.json`
- **Name**: Complete Information
- **Description**: Comprehensive overlay with timelapse name, weather, timestamp, and frame count
- **Use Case**: Professional timelapses requiring full metadata
- **Features**: All four corners utilized with different data types

## Template Structure

Each template file follows this JSON structure:

```json
{
  "name": "Template Name",
  "description": "Template description",
  "overlay_config": {
    "overlayPositions": {
      "topLeft": { /* overlay item config */ },
      "topRight": { /* overlay item config */ },
      "bottomLeft": { /* overlay item config */ },
      "bottomRight": { /* overlay item config */ }
    },
    "globalOptions": { /* global styling options */ }
  },
  "is_builtin": true
}
```

## Overlay Item Types

- `date_time`: Date and time display
- `weather_temp_conditions`: Weather temperature and conditions
- `timelapse_name`: Name of the timelapse
- `frame_number`: Current frame number
- `custom_text`: Static custom text

## Usage in Docker Deployments

Templates are automatically initialized during fresh database setup:

1. **Automatic**: Called during `initialize_database()` for fresh deployments
2. **Manual**: Run `python3 init_templates.py` to initialize templates
3. **Status**: Run `python3 init_templates.py --status` to check template status

## Template Management

### Adding New Templates

1. Create a new JSON file in this directory
2. Follow the template structure above
3. Run `python3 init_templates.py` to initialize the new template

### Modifying Templates

Templates are only inserted if they don't already exist (by name). To update:

1. Modify the JSON file
2. Delete the existing preset from the database
3. Run `python3 init_templates.py` to re-initialize

### Docker Integration

The template initialization is integrated into the database initialization process:

- Fresh databases automatically get templates seeded
- Existing databases are not affected
- Template initialization failures don't prevent database setup

## CLI Commands

```bash
# Initialize all templates
python3 init_templates.py

# Check template status
python3 init_templates.py --status

# Get JSON output
python3 init_templates.py --status --json

# Use custom database URL
python3 init_templates.py --database-url "postgresql://..."
```