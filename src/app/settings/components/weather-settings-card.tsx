// src/app/settings/components/weather-settings-card.tsx
"use client"

import { useState, useEffect } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { 
  Cloud, 
  MapPin, 
  Sunrise, 
  Sunset, 
  Check, 
  X, 
  RefreshCw,
  ExternalLink,
  Thermometer,
  Eye
} from "lucide-react"
import { toast } from "@/lib/toast"
import type { WeatherData, WeatherApiKeyValidationResponse } from "@/types"

interface WeatherSettingsCardProps {
  weatherEnabled: boolean
  setWeatherEnabled: (value: boolean) => void
  sunriseSunsetEnabled: boolean
  setSunriseSunsetEnabled: (value: boolean) => void
  latitude: number | null
  setLatitude: (value: number | null) => void
  longitude: number | null
  setLongitude: (value: number | null) => void
  openWeatherApiKey: string
  apiKeyModified: boolean
  originalApiKeyHash: string
}

export function WeatherSettingsCard({
  weatherEnabled,
  setWeatherEnabled,
  sunriseSunsetEnabled,
  setSunriseSunsetEnabled,
  latitude,
  setLatitude,
  longitude,
  setLongitude,
  openWeatherApiKey,
  apiKeyModified,
  originalApiKeyHash,
}: WeatherSettingsCardProps) {
  const [weatherData, setWeatherData] = useState<WeatherData | null>(null)
  const [validatingApiKey, setValidatingApiKey] = useState(false)
  const [apiKeyValid, setApiKeyValid] = useState<boolean | null>(null)
  const [refreshingWeather, setRefreshingWeather] = useState(false)

  // Fetch current weather data
  const fetchWeatherData = async () => {
    try {
      const response = await fetch("/api/settings/weather/data")
      if (response.ok) {
        const data = await response.json()
        setWeatherData(data)
      }
    } catch (error) {
      console.error("Failed to fetch weather data:", error)
    }
  }

  // Validate API key
  const validateApiKey = async () => {
    if (!openWeatherApiKey.trim() || !latitude || !longitude) {
      setApiKeyValid(null)
      return
    }

    setValidatingApiKey(true)
    try {
      const response = await fetch("/api/settings/weather/validate-api-key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_key: openWeatherApiKey,
          latitude: latitude,
          longitude: longitude,
        }),
      })

      const result: WeatherApiKeyValidationResponse = await response.json()
      setApiKeyValid(result.valid)

      if (result.valid) {
        toast.success("API key validated", {
          description: "OpenWeather API key is working correctly",
        })
      } else {
        toast.error("API key validation failed", {
          description: result.message,
        })
      }
    } catch (error) {
      console.error("API key validation error:", error)
      setApiKeyValid(false)
      toast.error("Validation error", {
        description: "Failed to validate API key",
      })
    } finally {
      setValidatingApiKey(false)
    }
  }

  // Refresh weather data
  const refreshWeatherData = async () => {
    setRefreshingWeather(true)
    try {
      const response = await fetch("/api/settings/weather/refresh", {
        method: "POST",
      })

      const result = await response.json()
      if (result.success) {
        setWeatherData(result.weather_data)
        toast.success("Weather data refreshed", {
          description: "Successfully fetched latest weather information",
        })
      } else {
        toast.error("Failed to refresh weather", {
          description: result.message,
        })
      }
    } catch (error) {
      console.error("Weather refresh error:", error)
      toast.error("Refresh error", {
        description: "Failed to refresh weather data",
      })
    } finally {
      setRefreshingWeather(false)
    }
  }

  // Get weather icon URL
  const getWeatherIconUrl = (icon: string) => {
    return `https://openweathermap.org/img/wn/${icon}@2x.png`
  }

  useEffect(() => {
    fetchWeatherData()
  }, [])

  // Check if we have an API key (either stored or currently entered)
  const hasApiKey = (originalApiKeyHash && originalApiKeyHash.trim()) || (apiKeyModified && openWeatherApiKey.trim())
  const canUseWeather = hasApiKey && latitude && longitude
  const locationComplete = latitude !== null && longitude !== null

  return (
    <Card className="transition-all duration-300 glass hover:glow">
      <CardHeader>
        <CardTitle className="flex items-center space-x-2">
          <Cloud className="w-5 h-5 text-blue-400" />
          <span>Weather Integration</span>
          {weatherEnabled && canUseWeather && (
            <Badge variant="secondary" className="ml-2 text-xs bg-green-500/20 text-green-300 border-green-500/30">
              Active
            </Badge>
          )}
        </CardTitle>
        <CardDescription>
          Configure OpenWeather integration for weather data collection and sunrise/sunset time windows
        </CardDescription>
      </CardHeader>
      
      <CardContent className="space-y-6">
        {/* Location Configuration */}
        <div className="space-y-4">
          <div className="flex items-center space-x-2">
            <MapPin className="w-4 h-4 text-blue-400" />
            <Label className="text-sm font-medium">Location Coordinates</Label>
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="latitude" className="text-xs text-muted-foreground">
                Latitude (-90 to 90)
              </Label>
              <Input
                id="latitude"
                type="number"
                step="0.000001"
                min="-90"
                max="90"
                value={latitude || ""}
                onChange={(e) => {
                  const value = e.target.value
                  setLatitude(value ? parseFloat(value) : null)
                }}
                placeholder="e.g., 40.7128"
                className="bg-background/50 border-borderColor/50 focus:border-primary/50"
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="longitude" className="text-xs text-muted-foreground">
                Longitude (-180 to 180)
              </Label>
              <Input
                id="longitude"
                type="number"
                step="0.000001"
                min="-180"
                max="180"
                value={longitude || ""}
                onChange={(e) => {
                  const value = e.target.value
                  setLongitude(value ? parseFloat(value) : null)
                }}
                placeholder="e.g., -74.0060"
                className="bg-background/50 border-borderColor/50 focus:border-primary/50"
              />
            </div>
          </div>
          
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              Use a service like{" "}
              <a 
                href="https://www.latlong.net/" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-primary hover:text-primary/80 inline-flex items-center"
              >
                latlong.net <ExternalLink className="w-3 h-3 ml-1" />
              </a>{" "}
              to find your coordinates
            </p>
            {locationComplete && (
              <Badge variant="outline" className="text-xs text-green-300 border-green-500/30">
                <Check className="w-3 h-3 mr-1" />
                Location Set
              </Badge>
            )}
          </div>
        </div>

        <Separator />

        {/* Weather Data Collection */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <Label className="text-sm font-medium">Weather Data Collection</Label>
              <p className="text-xs text-muted-foreground">
                Record weather conditions during image captures
              </p>
            </div>
            <Switch
              checked={weatherEnabled}
              onCheckedChange={setWeatherEnabled}
              disabled={!canUseWeather}
            />
          </div>

          {weatherEnabled && !canUseWeather && (
            <Alert>
              <AlertDescription className="text-xs">
                Weather data collection requires a valid API key and location coordinates.
              </AlertDescription>
            </Alert>
          )}

          {/* Current Weather Display */}
          {weatherData && (
            <div className="bg-muted/30 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-medium">Current Weather</h4>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={refreshWeatherData}
                  disabled={refreshingWeather || !canUseWeather}
                  className="h-8 px-3"
                >
                  {refreshingWeather ? (
                    <RefreshCw className="w-3 h-3 animate-spin" />
                  ) : (
                    <RefreshCw className="w-3 h-3" />
                  )}
                </Button>
              </div>
              
              <div className="flex items-center space-x-4">
                {weatherData.icon && (
                  <img
                    src={getWeatherIconUrl(weatherData.icon)}
                    alt={weatherData.description || "Weather"}
                    className="w-12 h-12"
                  />
                )}
                <div className="space-y-1">
                  {weatherData.temperature && (
                    <div className="flex items-center space-x-2">
                      <Thermometer className="w-4 h-4 text-orange-400" />
                      <span className="text-lg font-medium">{weatherData.temperature}°C</span>
                    </div>
                  )}
                  {weatherData.description && (
                    <p className="text-sm text-muted-foreground capitalize">
                      {weatherData.description}
                    </p>
                  )}
                  {weatherData.date_fetched && (
                    <p className="text-xs text-muted-foreground">
                      Updated: {new Date(weatherData.date_fetched).toLocaleDateString()}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* API Key Validation */}
          {hasApiKey && locationComplete && (
            <div className="flex items-center space-x-2">
              <Button
                size="sm"
                variant="outline"
                onClick={validateApiKey}
                disabled={validatingApiKey}
                className="h-8"
              >
                {validatingApiKey ? (
                  <RefreshCw className="w-3 h-3 mr-2 animate-spin" />
                ) : (
                  <Eye className="w-3 h-3 mr-2" />
                )}
                Test API Key
              </Button>
              
              {apiKeyValid !== null && (
                <Badge 
                  variant={apiKeyValid ? "secondary" : "destructive"}
                  className={apiKeyValid 
                    ? "text-green-300 border-green-500/30 bg-green-500/20" 
                    : "text-red-300 border-red-500/30 bg-red-500/20"
                  }
                >
                  {apiKeyValid ? (
                    <>
                      <Check className="w-3 h-3 mr-1" />
                      Valid
                    </>
                  ) : (
                    <>
                      <X className="w-3 h-3 mr-1" />
                      Invalid
                    </>
                  )}
                </Badge>
              )}
            </div>
          )}
        </div>

        <Separator />

        {/* Sunrise/Sunset Time Windows */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <Label className="text-sm font-medium">Sunrise/Sunset Time Windows</Label>
              <p className="text-xs text-muted-foreground">
                Enable sunrise and sunset time windows for timelapse configuration. Specific offsets are configured per-timelapse.
              </p>
            </div>
            <Switch
              checked={sunriseSunsetEnabled}
              onCheckedChange={setSunriseSunsetEnabled}
              disabled={!canUseWeather}
            />
          </div>

          {sunriseSunsetEnabled && !canUseWeather && (
            <Alert>
              <AlertDescription className="text-xs">
                Sunrise/sunset time windows require a valid API key and location coordinates.
              </AlertDescription>
            </Alert>
          )}

          {/* Sun Times Display */}
          {sunriseSunsetEnabled && weatherData?.sunrise_timestamp && weatherData?.sunset_timestamp && (
            <div className="bg-muted/30 rounded-lg p-4">
              <h5 className="text-xs font-medium text-muted-foreground mb-2">Today's Sun Times</h5>
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div className="flex items-center space-x-2">
                  <Sunrise className="w-3 h-3 text-yellow-400" />
                  <span>
                    {new Date(weatherData.sunrise_timestamp * 1000).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </span>
                </div>
                <div className="flex items-center space-x-2">
                  <Sunset className="w-3 h-3 text-orange-400" />
                  <span>
                    {new Date(weatherData.sunset_timestamp * 1000).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
