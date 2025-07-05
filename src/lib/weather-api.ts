// src/lib/weather-api.ts
export interface WeatherData {
  temperature: number
  condition: string
  description: string
  icon: string
  cityName: string
  countryCode: string
}

export interface ApiKeyValidationResult {
  isValid: boolean
  error?: string
  message?: string
  weatherData?: WeatherData
}

/**
 * Test OpenWeather API key and fetch current weather data
 */
export async function validateApiKeyAndFetchWeather(
  apiKey: string,
  latitude: number,
  longitude: number
): Promise<ApiKeyValidationResult> {
  if (!apiKey || !apiKey.trim()) {
    return {
      isValid: false,
      error: "API key is required"
    }
  }

  // Validate API key format (OpenWeather keys are 32 character hex strings)
  const apiKeyPattern = /^[a-f0-9]{32}$/i
  if (!apiKeyPattern.test(apiKey.trim())) {
    console.log(`🔍 API key validation failed for: "${apiKey}" (length: ${apiKey.length})`)
    return {
      isValid: false,
      error: "Invalid API key format (must be 32 hexadecimal characters)"
    }
  }

  if (typeof latitude !== 'number' || typeof longitude !== 'number') {
    return {
      isValid: false,
      error: "Location coordinates must be numbers"
    }
  }

  if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
    return {
      isValid: false,
      error: "Invalid coordinate range"
    }
  }

  try {
    // Use current weather API endpoint
    const weatherUrl = `https://api.openweathermap.org/data/2.5/weather?lat=${latitude}&lon=${longitude}&appid=${apiKey}&units=metric`
    
    const response = await fetch(weatherUrl)
    
    if (!response.ok) {
      if (response.status === 401) {
        return {
          isValid: false,
          error: "Invalid API key"
        }
      } else if (response.status === 429) {
        return {
          isValid: false,
          error: "API rate limit exceeded"
        }
      } else {
        return {
          isValid: false,
          error: `API error: ${response.status}`
        }
      }
    }

    const data = await response.json()
    
    // Validate API response structure
    if (!data || !data.main || !data.weather || !Array.isArray(data.weather) || data.weather.length === 0) {
      return {
        isValid: false,
        error: "Invalid weather data received"
      }
    }
    
    // Reverse geocoding for city name
    let cityName = "Unknown Location"
    let countryCode = ""
    
    try {
      const geocodeUrl = `https://api.openweathermap.org/geo/1.0/reverse?lat=${latitude}&lon=${longitude}&limit=1&appid=${apiKey}`
      const geocodeResponse = await fetch(geocodeUrl)
      
      if (geocodeResponse.ok) {
        const geocodeData = await geocodeResponse.json()
        if (geocodeData && geocodeData.length > 0) {
          cityName = geocodeData[0].name || "Unknown Location"
          countryCode = geocodeData[0].country || ""
        }
      }
    } catch (geocodeError) {
      // Fallback to weather API's name if reverse geocoding fails
      cityName = data.name || "Unknown Location"
      countryCode = data.sys?.country || ""
    }

    const weatherData: WeatherData = {
      temperature: Math.round(data.main.temp || 0),
      condition: data.weather[0].main || "Unknown",
      description: data.weather[0].description || "Unknown conditions",
      icon: data.weather[0].icon || "01d",
      cityName,
      countryCode
    }

    return {
      isValid: true,
      weatherData
    }
  } catch (error) {
    return {
      isValid: false,
      error: error instanceof Error ? error.message : "Network error"
    }
  }
}

/**
 * Get weather icon component based on OpenWeather icon code
 */
export function getWeatherIcon(iconCode: string): string {
  // OpenWeather icon codes mapping to emoji
  const iconMap: Record<string, string> = {
    '01d': '☀️', // clear sky day
    '01n': '🌙', // clear sky night
    '02d': '⛅', // few clouds day
    '02n': '☁️', // few clouds night
    '03d': '☁️', // scattered clouds
    '03n': '☁️', // scattered clouds
    '04d': '☁️', // broken clouds
    '04n': '☁️', // broken clouds
    '09d': '🌧️', // shower rain
    '09n': '🌧️', // shower rain
    '10d': '🌦️', // rain day
    '10n': '🌧️', // rain night
    '11d': '⛈️', // thunderstorm
    '11n': '⛈️', // thunderstorm
    '13d': '❄️', // snow
    '13n': '❄️', // snow
    '50d': '🌫️', // mist
    '50n': '🌫️', // mist
  }

  return iconMap[iconCode] || '🌤️'
}

/**
 * Format temperature with appropriate unit
 */
export function formatTemperature(temp: number): string {
  return `${temp}°C`
}

/**
 * Capitalize first letter of each word
 */
export function capitalizeWords(str: string): string {
  return str.replace(/\b\w/g, char => char.toUpperCase())
}