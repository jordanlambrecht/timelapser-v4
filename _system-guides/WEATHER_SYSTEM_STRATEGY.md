# Timelapser v4 Weather System Strategy Guide

> Last Updated: July 5th, 2025

## 🎯 Overview

This guide defines the architecture and implementation patterns for the weather integration system in Timelapser v4. The weather system provides OpenWeather API integration, sunrise/sunset calculations, and intelligent capture scheduling based on natural lighting conditions.

## 📚 The Three Core Components

### 1. **OpenWeatherService** - External API Integration

**What**: Direct interface to OpenWeather API for fetching weather data  
**When**: Raw weather data needed from external source  
**How**: Validates API keys, fetches current weather, handles API errors gracefully

### 2. **WeatherManager** - Data Coordination Layer

**What**: Coordinates between API service and database operations  
**When**: Weather data needs to be cached, validated, or processed  
**How**: Dependency injection pattern with weather operations for clean architecture

### 3. **Worker Integration** - Automated Data Refresh

**What**: Hourly weather data fetching and caching in background  
**When**: System needs fresh weather data without user interaction  
**How**: Scheduled jobs in AsyncTimelapseWorker with proper error handling

---

## 🎲 Decision Matrix

| Component                 | Responsibility            | Used By              | Why                                    |
| ------------------------- | ------------------------- | -------------------- | -------------------------------------- |
| **OpenWeatherService**    | API calls & validation    | WeatherManager       | Clean external API abstraction         |
| **WeatherManager**        | Data coordination         | Worker, Settings     | Business logic layer with DI           |
| **Weather Operations**    | Database access           | WeatherManager       | Proper data layer separation           |
| **Weather Models**        | Data validation           | All components       | Type safety and data consistency       |
| **Worker Integration**    | Automated refresh         | Background process   | Reliable hourly updates without user   |
| **Settings Integration**  | Configuration             | Frontend, Manager    | User control over weather features     |

---

## 🚀 Strategy Details

### OpenWeatherService Strategy: API Abstraction

**Use When:**
- Need to fetch current weather data
- Validating API keys
- Calculating sunrise/sunset time windows
- Converting timestamps to local time zones

**Implementation:**

```python
from app.models.weather_model import OpenWeatherApiData, WeatherApiValidationResponse
from app.constants import OPENWEATHER_API_BASE_URL, OPENWEATHER_API_TIMEOUT

class OpenWeatherService:
    BASE_URL = OPENWEATHER_API_BASE_URL
    
    def __init__(self, api_key: str, latitude: float, longitude: float):
        self.api_key = api_key
        self.latitude = latitude
        self.longitude = longitude
    
    def validate_api_key(self) -> WeatherApiValidationResponse:
        """Validate API key with proper error handling"""
        try:
            response = requests.get(self.BASE_URL, params={...}, timeout=OPENWEATHER_API_TIMEOUT)
            if response.status_code == 200:
                return WeatherApiValidationResponse(
                    valid=True, message=WEATHER_API_KEY_VALID, status=WeatherApiStatus.VALID
                )
            # Handle various error codes...
        except requests.exceptions.RequestException as e:
            return WeatherApiValidationResponse(
                valid=False, message=f"{WEATHER_CONNECTION_ERROR}: {str(e)}", 
                status=WeatherApiStatus.FAILING
            )
    
    def fetch_current_weather(self) -> Optional[OpenWeatherApiData]:
        """Fetch and parse weather data into Pydantic model"""
        # API call and data transformation logic
```

**Examples in Timelapser:**
- API key validation in settings
- Hourly weather data fetching
- Sunrise/sunset time calculations
- Time window validation for capture scheduling

---

### WeatherManager Strategy: Dependency Injection Coordination

**Use When:**
- Coordinating between API service and database
- Processing weather data for storage
- Managing API failures and error tracking
- Providing weather data to other services

**Implementation:**

```python
from app.models.weather_model import OpenWeatherApiData, WeatherDataRecord
from app.constants import WEATHER_REFRESH_SKIPPED_LOCATION

class WeatherManager:
    """Weather data coordination with dependency injection"""
    
    def __init__(self, weather_operations, settings_service=None):
        """Initialize with injected dependencies - no direct DB access"""
        self.weather_ops = weather_operations  # Injected weather operations
        self.settings_service = settings_service
    
    async def update_weather_cache(self, weather_data: OpenWeatherApiData) -> bool:
        """Store weather data using injected operations"""
        try:
            # Convert API data for database storage
            weather_date_fetched = datetime.combine(weather_data.date_fetched, datetime.min.time())
            
            # Use injected operations (async/sync automatically handled)
            if inspect.iscoroutinefunction(self.weather_ops.insert_weather_data):
                weather_id = await self.weather_ops.insert_weather_data(...)
            else:
                weather_id = self.weather_ops.insert_weather_data(...)
                
            logger.info(f"Weather cache updated (ID: {weather_id}): {weather_data.temperature}°C")
            return True
        except Exception as e:
            logger.error(f"Failed to update weather cache: {e}")
            return False
    
    async def refresh_weather_if_needed(self, api_key: str) -> Optional[OpenWeatherApiData]:
        """Smart refresh logic with proper error handling"""
        # Check if location is configured
        settings = await self.get_weather_settings()
        if not settings.get("latitude") or not settings.get("longitude"):
            logger.warning(WEATHER_REFRESH_SKIPPED_LOCATION)
            return None
            
        # Check if data is current using injected operations
        latest_weather = await self.weather_ops.get_latest_weather()
        # Refresh logic with timezone awareness...
```

**Architecture Benefits:**
- Clean separation of concerns
- Dependency injection for testability
- No direct database imports in service layer
- Proper error handling and logging
- Constants usage instead of hardcoded values

---

## 🏗️ Weather System Architecture Implementation

The weather system implements a clean three-layer architecture with proper dependency injection, Pydantic validation, and automated background processing.

### Architecture Overview

```
OpenWeatherService    WeatherManager       Weather Operations
     ↓                      ↓                      ↓
 API Abstraction     Business Logic         Data Layer
- API calls          - Coordination         - Database access
- Validation         - Error tracking       - CRUD operations  
- Data parsing       - Cache management     - Query optimization
- Time calculations  - Settings integration - Transaction handling
```

**Design Principle**: Separation of concerns with dependency injection

---

### 📦 Core Classes Reference

#### `OpenWeatherApiData` (weather_model.py)

Pydantic model for raw weather data from OpenWeather API.

```python
class OpenWeatherApiData(BaseModel):
    temperature: int = Field(..., description="Temperature in Celsius")
    icon: str = Field(..., max_length=50, description="OpenWeather icon code")
    description: str = Field(..., max_length=255, description="Weather description")
    sunrise_timestamp: int = Field(..., description="Sunrise Unix timestamp")
    sunset_timestamp: int = Field(..., description="Sunset Unix timestamp")
    date_fetched: date = Field(..., description="Date when weather was fetched")
```

**When to use**: Return type from OpenWeatherService.fetch_current_weather()

#### `WeatherDataRecord` (weather_model.py)

Complete weather record as stored in weather_data table.

```python
class WeatherDataRecord(BaseModel):
    id: Optional[int] = Field(None, description="Database record ID")
    weather_date_fetched: Optional[datetime] = Field(None, description="When weather was fetched")
    current_temp: Optional[float] = Field(None, description="Temperature in Celsius")
    api_key_valid: Optional[bool] = Field(True, description="Whether API key is valid")
    api_failing: Optional[bool] = Field(False, description="Whether API is failing")
    consecutive_failures: Optional[int] = Field(0, description="Number of consecutive failures")
    # ... other fields for complete weather record
```

**When to use**: Database operations and full weather record handling

#### `SunTimeWindow` (weather_model.py)

Time window calculation for sunrise/sunset based capture scheduling.

```python
class SunTimeWindow(BaseModel):
    start_time: time = Field(..., description="Window start time")
    end_time: time = Field(..., description="Window end time")
    is_overnight: bool = Field(False, description="True if window spans midnight")
    
    @field_validator('start_time', 'end_time')
    @classmethod
    def validate_time_format(cls, v):
        if not isinstance(v, time):
            raise ValueError('Must be a time object')
        return v
```

**When to use**: Capture scheduling and time window calculations

#### `WeatherOperations` (weather_operations.py)

Database operations for weather data with async/sync variants.

```python
class WeatherOperations:
    async def get_latest_weather(self) -> Optional[Dict[str, Any]]
    async def insert_weather_data(...) -> int
    async def update_weather_failure(...) -> None
    async def get_weather_for_hour(target_datetime: datetime) -> Optional[Dict[str, Any]]

class SyncWeatherOperations:
    def get_latest_weather(self) -> Optional[Dict[str, Any]]
    def insert_weather_data(...) -> int
    def update_weather_failure(...) -> None
    # Sync versions of all operations
```

**When to use**: 
- Inject into WeatherManager for database access
- Use SyncWeatherOperations in worker (sync context)
- Use WeatherOperations in async API routes

---

### 🎯 Integration Patterns

#### Pattern 1: Worker Background Refresh

```python
class AsyncTimelapseWorker:
    def __init__(self):
        # Proper dependency injection in worker
        weather_ops = SyncWeatherOperations(sync_db)
        self.weather_manager = WeatherManager(weather_ops, self.settings_service)
    
    async def refresh_weather_data(self):
        """Scheduled weather refresh with proper error handling"""
        try:
            # Check if weather is enabled
            settings_dict = await asyncio.get_event_loop().run_in_executor(
                None, self.settings_service.get_all_settings
            )
            
            if settings_dict.get("weather_enabled", "false").lower() != "true":
                logger.debug(WEATHER_REFRESH_SKIPPED_DISABLED)
                return
            
            # Get API key securely
            api_key = await asyncio.get_event_loop().run_in_executor(
                None, self.settings_service.get_openweather_api_key
            )
            
            # Refresh weather data
            weather_data = await self.weather_manager.refresh_weather_if_needed(api_key)
            if weather_data:
                logger.info(f"Weather refreshed: {weather_data.temperature}°C")
                
                # Broadcast SSE event for real-time updates
                await loop.run_in_executor(None, self.sse_ops.create_event, 
                    "weather_updated", {...})
        except Exception as e:
            logger.error(f"Error refreshing weather data: {e}")

    async def start(self):
        # Schedule weather refresh every hour
        self.scheduler.add_job(
            func=self.refresh_weather_data,
            trigger="cron", minute=0,  # Top of every hour
            id="weather_job", name="Refresh Weather Data",
            max_instances=1
        )
```

#### Pattern 2: Settings Integration

```python
# Settings router integration
@router.get("/settings")
async def get_settings():
    # Get regular settings
    settings_dict = await settings_service.get_all_settings()
    
    # Get latest weather data and merge for backward compatibility
    weather_ops = WeatherOperations(db)
    weather_data = await weather_ops.get_latest_weather()
    
    if weather_data:
        settings_dict["weather_date_fetched"] = weather_data.get("weather_date_fetched", "").isoformat()
        settings_dict["current_temp"] = str(weather_data.get("current_temp", ""))
        # ... merge other weather fields
    
    return ResponseFormatter.success(data=settings_dict)

# Weather validation endpoint
@router.post("/weather/validate-api-key")
async def validate_weather_api_key(request: WeatherApiValidationRequest):
    service = OpenWeatherService(
        api_key=request.api_key,
        latitude=request.latitude or 40.7128,  # Default to NYC
        longitude=request.longitude or -74.0060
    )
    
    result = service.validate_api_key()
    return ResponseFormatter.success(data=result.dict())
```

#### Pattern 3: Capture Time Window Integration

```python
# In worker capture logic
def _check_sun_based_window(self, settings_dict: dict) -> bool:
    """Check if current time is within sunrise/sunset window"""
    try:
        # Get weather data from weather_data table
        weather_ops = SyncWeatherOperations(sync_db)
        latest_weather = weather_ops.get_latest_weather()
        
        if not latest_weather:
            return True  # Allow capture if no weather data
            
        # Extract sunrise/sunset timestamps
        sunrise_timestamp = latest_weather.get("sunrise_timestamp")
        sunset_timestamp = latest_weather.get("sunset_timestamp")
        
        if not sunrise_timestamp or not sunset_timestamp:
            return True
        
        # Convert datetime objects to timestamps if needed
        if isinstance(sunrise_timestamp, datetime):
            sunrise_timestamp = int(sunrise_timestamp.timestamp())
        if isinstance(sunset_timestamp, datetime):
            sunset_timestamp = int(sunset_timestamp.timestamp())
            
        # Use OpenWeatherService for time window calculation
        service = OpenWeatherService("dummy", 0, 0)  # API key not needed for calculations
        return service.is_within_sun_window(
            sunrise_timestamp=sunrise_timestamp,
            sunset_timestamp=sunset_timestamp,
            sunrise_offset_minutes=int(settings_dict.get("sunrise_offset_minutes", 0)),
            sunset_offset_minutes=int(settings_dict.get("sunset_offset_minutes", 0)),
            timezone_str=settings_dict.get("timezone", "UTC")
        )
    except Exception as e:
        logger.warning(f"Error checking sun-based window: {e}")
        return True  # Fail open
```

---

## 🛠️ Implementation Guidelines

### Service Layer (Business Logic)

```python
# ✅ WeatherManager coordinates but doesn't access database directly
class WeatherManager:
    def __init__(self, weather_operations, settings_service=None):
        self.weather_ops = weather_operations  # Injected dependency
        self.settings_service = settings_service
    
    async def refresh_weather_if_needed(self, api_key: str):
        # Uses injected weather_ops for database access
        latest_weather = await self.weather_ops.get_latest_weather()
        # Business logic...
```

### Database Layer (Stay Pure)

```python
# ✅ Weather operations don't know about business logic
class WeatherOperations:
    async def get_latest_weather(self) -> Optional[Dict[str, Any]]:
        # Pure data access, no business logic
        async with await self.db.get_connection() as conn:
            result = await conn.execute(text("""
                SELECT * FROM weather_data 
                ORDER BY weather_date_fetched DESC 
                LIMIT 1
            """))
            row = result.fetchone()
            return dict(row._mapping) if row else None
```

### Constants Usage

```python
# ✅ Use constants instead of hardcoded values
from app.constants import (
    OPENWEATHER_API_BASE_URL,
    OPENWEATHER_API_TIMEOUT,
    WEATHER_MAX_CONSECUTIVE_FAILURES,
    WEATHER_API_KEY_VALID
)

class OpenWeatherService:
    BASE_URL = OPENWEATHER_API_BASE_URL
    
    def validate_api_key(self):
        response = requests.get(self.BASE_URL, timeout=OPENWEATHER_API_TIMEOUT)
        if response.status_code == 200:
            return WeatherApiValidationResponse(message=WEATHER_API_KEY_VALID)
```

---

## 📊 Performance Impact

### Without Weather Integration

```bash
Capture scheduling: Manual time windows only
Seasonal adaptation: Manual schedule updates required
Weather context: No weather information in timelapses
```

### With Weather Integration

```bash
Capture scheduling: Automatic sunrise/sunset adaptation
Seasonal adaptation: Zero manual intervention needed
Weather context: Temperature and conditions logged with captures
API efficiency: 24 calls/day (hourly) well within free tier (1000/month)
```

---

## ⚠️ Common Pitfalls

### 1. **Direct Database Access in Services**

```python
# ❌ Don't import database operations directly in services
from app.database.weather_operations import WeatherOperations
class WeatherManager:
    def __init__(self):
        self.weather_ops = WeatherOperations(db)  # Violates DI pattern

# ✅ Use dependency injection
class WeatherManager:
    def __init__(self, weather_operations):
        self.weather_ops = weather_operations  # Injected dependency
```

### 2. **Hardcoded Values Instead of Constants**

```python
# ❌ Hardcoded API URLs and timeouts
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
timeout = 10

# ✅ Use constants
from app.constants import OPENWEATHER_API_BASE_URL, OPENWEATHER_API_TIMEOUT
BASE_URL = OPENWEATHER_API_BASE_URL
timeout = OPENWEATHER_API_TIMEOUT
```

### 3. **Mixing Pydantic Versions**

```python
# ❌ Using deprecated Pydantic v1 patterns
from pydantic import validator
@validator('field')
def validate_field(cls, v):

# ✅ Use Pydantic v2 patterns
from pydantic import field_validator
@field_validator('field')
@classmethod
def validate_field(cls, v):
```

### 4. **API Key Security Issues**

```python
# ❌ Passing API keys as plain strings everywhere
def fetch_weather(api_key: str):
    # API key exposed in logs, memory dumps, etc.

# ✅ Use secure API key handling through settings service
api_key = settings_service.get_openweather_api_key()  # Properly encrypted/decrypted
```

---

## 🎯 Timelapser-Specific Rules

### Weather Data Refresh

```python
# Rule: Hourly refresh in worker, not on-demand in API routes
# Why: Predictable API usage, better performance, offline resilience
```

### API Failure Handling

```python
# Rule: Track consecutive failures, implement exponential backoff
consecutive_failures = weather_data.get("consecutive_failures", 0)
if consecutive_failures >= WEATHER_MAX_CONSECUTIVE_FAILURES:
    # Mark API as failing, reduce refresh frequency
```

### Time Zone Awareness

```python
# Rule: Always use timezone-aware datetime calculations
from app.utils.timezone_utils import get_timezone_from_settings
timezone_str = get_timezone_from_settings(settings_dict)
# All sunrise/sunset calculations must respect user timezone
```

### Settings Integration

```python
# Rule: Weather data included in settings response for backward compatibility
# Why: Frontend expects weather data in settings, gradual migration approach
```

---

## 🚦 Implementation Checklist

### For Weather Integration Development

1. **Model Design**
   - Use Pydantic v2 patterns with `field_validator`
   - Separate API models from database record models
   - Include proper field validation and descriptions

2. **Service Layer**
   - Implement dependency injection pattern
   - No direct database imports in service classes
   - Use constants instead of hardcoded values
   - Proper error handling with user-friendly messages

3. **Database Integration**
   - Separate weather_data table for clean architecture
   - Async and sync operation variants for flexibility
   - Proper transaction handling and error recovery

4. **Worker Integration**
   - Hourly refresh scheduling (cron: minute=0)
   - Graceful error handling with retry logic
   - SSE event broadcasting for real-time updates

5. **API Integration**
   - Secure API key handling through settings service
   - Proper timeout and retry mechanisms
   - Comprehensive API validation with clear error messages

### Testing Weather Components

```bash
# Test API integration
python -c "from app.services.weather.service import OpenWeatherService; ..."

# Test database operations
python -c "from app.database.weather_operations import SyncWeatherOperations; ..."

# Test worker integration
python worker.py  # Check logs for weather refresh

# Test settings integration
curl http://localhost:8000/api/settings  # Check weather data included
```

---

## 🎓 Summary

**The Three-Layer Architecture:**

1. **OpenWeatherService** for clean external API abstraction
2. **WeatherManager** for business logic coordination with dependency injection  
3. **Weather Operations** for pure database access without business concerns

**Golden Rules:**

- API calls: Hourly refresh in background worker only
- Data storage: Separate weather_data table with proper models
- Error handling: Track failures, implement graceful degradation
- Time calculations: Always timezone-aware with user preferences
- Settings integration: Backward compatible weather data inclusion

**Implementation:**

- Services use dependency injection (no direct DB imports)
- Constants file for all hardcoded values
- Pydantic v2 models for data validation
- Proper async/sync handling throughout the stack

This architecture provides reliable weather integration while maintaining clean separation of concerns and excellent testability.