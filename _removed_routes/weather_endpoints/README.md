# Removed Weather Endpoints

## Removed Routes (2025-01-01)

The following over-engineered weather endpoints were removed as part of API cleanup:

### `/api/settings/weather/data` (GET)
- **Reason**: Over-engineered - weather data comes automatically with images from background worker
- **Alternative**: Use automatic background weather collection
- **File**: `data_route.ts`

### `/api/settings/weather/refresh` (POST) 
- **Reason**: Over-engineered - weather updates happen automatically every hour
- **Alternative**: Use automatic background updates
- **File**: `refresh_route.ts`

### `/api/settings/weather/sun-window` (GET)
- **Reason**: Over-engineered - sunrise/sunset calculated automatically from stored data
- **Alternative**: Calculate time windows from stored weather data
- **File**: `sun-window_route.ts`

### `/api/settings/weather/validate-api-key` (POST)
- **Reason**: Over-engineered - can be part of main weather settings validation
- **Alternative**: Validate API key in main settings endpoint
- **File**: `validate-api-key_route.ts`

## Impact

- **API Surface Area**: Simplified from 8 weather endpoints to 4 core endpoints
- **Maintainability**: Reduced complexity by removing duplicate functionality
- **Performance**: Eliminated unnecessary API calls through better architecture
- **User Experience**: No impact - functionality moved to automatic background processes

## Core Weather Functionality Retained

- `/api/settings/weather` (GET, PUT) - Main weather settings management
- Background weather data collection - Automatic hourly updates
- Sunrise/sunset calculations - Computed from stored location data
- API key validation - Integrated into main settings validation

*These endpoints were removed as part of systematic API cleanup to reach 98%+ connectivity with clean, purpose-built endpoints only.*
