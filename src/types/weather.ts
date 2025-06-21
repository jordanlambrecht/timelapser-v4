// src/types/weather.ts
export interface WeatherSettings {
  latitude: number | null
  longitude: number | null
  weather_enabled: boolean
  sunrise_sunset_enabled: boolean
}

export interface WeatherData {
  temperature: number | null
  icon: string | null
  description: string | null
  date_fetched: string | null
  sunrise_timestamp: number | null
  sunset_timestamp: number | null
}

export interface WeatherApiKeyValidation {
  api_key: string
  latitude?: number
  longitude?: number
}

export interface WeatherApiKeyValidationResponse {
  valid: boolean
  message: string
}

export interface WeatherRefreshResponse {
  success: boolean
  message: string
  weather_data?: WeatherData
}

export interface SunTimeWindow {
  start_time: string
  end_time: string
  is_overnight: boolean
}

export interface TimeWindowMode {
  mode: 'none' | 'time' | 'sun'
  time_start?: string
  time_end?: string
  sunrise_offset?: number
  sunset_offset?: number
}
