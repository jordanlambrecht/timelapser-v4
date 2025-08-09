// src/hooks/use-weather-data.ts
"use client"

import { useState, useEffect } from "react"

interface WeatherData {
  current_temp?: number | null
  current_weather_description?: string
  current_weather_icon?: string
  weather_date_fetched?: string
  sunrise_timestamp?: string
  sunset_timestamp?: string
}

interface UseWeatherDataReturn {
  weatherData: WeatherData | null
  loading: boolean
  error: string | null
  refetch: () => void
}

export function useWeatherData(): UseWeatherDataReturn {
  const [weatherData, setWeatherData] = useState<WeatherData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchWeatherData = async () => {
    try {
      setLoading(true)
      setError(null)

      // Use dedicated weather endpoint for cleaner separation
      const response = await fetch("/api/weather/")

      if (!response.ok) {
        throw new Error(`Failed to fetch weather data: ${response.status}`)
      }

      const result = await response.json()

      if (result.success && result.data) {
        // Use weather data from dedicated endpoint
        const weatherData = result.data
        setWeatherData({
          current_temp: weatherData.current_temp
            ? parseFloat(weatherData.current_temp)
            : null,
          current_weather_description:
            weatherData.current_weather_description || null,
          current_weather_icon: weatherData.current_weather_icon || null,
          weather_date_fetched: weatherData.last_updated || null,
          sunrise_timestamp: weatherData.sunrise_timestamp || null,
          sunset_timestamp: weatherData.sunset_timestamp || null,
        })
      } else {
        setWeatherData(null)
      }
    } catch (err) {
      console.error("Failed to fetch weather data:", err)
      setError(
        err instanceof Error ? err.message : "Failed to fetch weather data"
      )
      setWeatherData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchWeatherData()
  }, [])

  return {
    weatherData,
    loading,
    error,
    refetch: fetchWeatherData,
  }
}
