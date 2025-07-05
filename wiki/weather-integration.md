# Weather Integration System

The Timelapser system automatically integrates with OpenWeather to provide weather data and intelligent capture scheduling based on sunrise and sunset times. This ensures your timelapses capture the best lighting conditions and can automatically adapt to seasonal changes.

## How It Works

Your Timelapser system fetches current weather data **every hour** and uses this information to:

- **Track sunrise and sunset times** for your exact location
- **Calculate optimal capture windows** based on natural lighting
- **Display current weather conditions** in the dashboard
- **Automatically adjust capture schedules** to avoid capturing in complete darkness

The system works completely automatically once configured, requiring no ongoing maintenance.

## Weather Data

### Current Conditions
- **Temperature** - Displayed in Celsius
- **Weather icon** - Visual representation of current conditions  
- **Description** - Text description (e.g., "clear sky", "light rain")
- **Data freshness** - Shows when weather was last updated

### Sunrise & Sunset Tracking
- **Precise timing** for your exact latitude and longitude
- **Automatic seasonal adjustment** - no manual updates needed
- **Timezone awareness** - calculations respect your configured timezone
- **Daily updates** - sunrise/sunset times refresh automatically

## Capture Window Features

### Sunrise/Sunset Based Scheduling

When enabled, your cameras will automatically:

- **Start capturing** at sunrise (or before with offset)
- **Stop capturing** at sunset (or after with offset)
- **Skip nighttime captures** to save storage and processing
- **Adapt to seasons** - longer days in summer, shorter in winter

### Time Window Customization

- **Sunrise offset** - Start capturing X minutes before/after sunrise
- **Sunset offset** - Stop capturing X minutes before/after sunset
- **Per-camera overrides** - Different cameras can have different schedules
- **Manual time windows** - Fixed times if you prefer not to use sun-based timing

## Configuration

### Required Settings

1. **OpenWeather API Key** - Free account at openweathermap.org
2. **Location coordinates** - Your latitude and longitude
3. **Enable weather integration** - Turn the system on/off

### API Key Setup

1. Visit [OpenWeather](https://openweathermap.org/api) and create a free account
2. Generate an API key from your account dashboard
3. Enter the API key in Timelapser Settings → Weather Integration
4. The system will automatically validate your key

### Location Configuration

Enter your coordinates in decimal format:
- **Latitude**: -90 to +90 (negative for Southern Hemisphere)
- **Longitude**: -180 to +180 (negative for Western Hemisphere)

*Tip: You can find your coordinates using Google Maps or GPS coordinates websites*

### Sunrise/Sunset Settings

- **Enable sunrise/sunset mode** - Use natural lighting for capture windows
- **Sunrise offset** - Minutes to adjust sunrise time (+ for later, - for earlier)  
- **Sunset offset** - Minutes to adjust sunset time (+ for later, - for earlier)

## Camera Integration

### Global vs Per-Camera Settings

**Global sunrise/sunset** affects all cameras unless overridden:
- All cameras follow the same sun-based schedule
- Consistent lighting conditions across all timelapses
- Simplest setup for most users

**Per-camera time windows** allow individual control:
- Some cameras can use sunrise/sunset timing
- Others can use fixed time windows  
- Useful for mixing indoor/outdoor cameras

### Time Window Priority

The system follows this priority order:
1. **Custom time window** (if enabled for that camera)
2. **Sunrise/sunset window** (if enabled globally)
3. **24/7 capture** (if no time restrictions)

## Monitoring & Status

### Weather Status Indicators

- **Green**: Weather data is current and API is working
- **Yellow**: Weather data is slightly stale but usable
- **Red**: Weather system has errors or data is very old

### API Validation

The system continuously monitors your OpenWeather API:
- **Real-time validation** when you enter your API key
- **Automatic retry** if API calls temporarily fail
- **Error tracking** to identify persistent issues
- **Fallback behavior** when weather data is unavailable

### Troubleshooting

**"API key invalid"** - Check your OpenWeather API key is correct and active

**"Location invalid"** - Verify your latitude/longitude coordinates are in valid ranges

**"Weather data stale"** - System will retry automatically; check your internet connection

**"API failing"** - Temporary OpenWeather service issues; system will recover automatically

## Privacy & Data Usage

### What Data Is Collected
- Current weather conditions for your location
- Sunrise/sunset times calculated from your coordinates
- No personal information is sent to OpenWeather

### API Usage
- Weather data is fetched once per hour
- Well within OpenWeather's free tier limits (1000 calls/month)
- No additional costs for normal usage

### Data Storage
- Weather data is stored locally in your Timelapser database
- No weather data is sent to external services
- All API communications are encrypted (HTTPS)

## Advanced Features

### Seasonal Adaptation

Your timelapses automatically adapt to seasons:
- **Summer**: Longer capture days (sunrise ~5:30am, sunset ~8:30pm)  
- **Winter**: Shorter capture days (sunrise ~7:30am, sunset ~4:30pm)
- **Spring/Fall**: Gradually adjusting capture windows

### Smart Scheduling

The system optimizes captures based on natural lighting:
- **Golden hour captures** - Best lighting conditions
- **Avoid complete darkness** - Save storage and processing
- **Consistent lighting** - Better timelapse quality
- **Automatic adjustment** - No manual schedule updates needed

## Best Practices

### For Outdoor Cameras
- Enable sunrise/sunset mode for natural lighting
- Use small offsets (15-30 minutes) to capture twilight
- Consider weather conditions when reviewing timelapses

### For Indoor Cameras  
- Use fixed time windows instead of sunrise/sunset
- Coordinate with building lighting schedules
- Consider mixing with outdoor cameras for context

### For Mixed Setups
- Use per-camera time windows for flexibility
- Group similar cameras with similar schedules
- Monitor capture counts to ensure desired coverage

The weather integration system is designed to work automatically while giving you complete control when needed. Most users can simply configure their API key and location, then let the system handle everything else.