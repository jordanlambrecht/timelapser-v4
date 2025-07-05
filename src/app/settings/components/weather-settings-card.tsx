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
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { 
  Cloud, 
  MapPin, 
  Check, 
  ExternalLink
} from "lucide-react"
import { useSettings } from "@/contexts/settings-context"

export function WeatherSettingsCard() {
  const {
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
  } = useSettings()
  
  // Local state for validation errors
  const [latError, setLatError] = useState<string | null>(null)
  const [lngError, setLngError] = useState<string | null>(null)
  
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
          Configure OpenWeather integration for automatic weather data collection and sunrise/sunset time windows
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
                  if (value === "") {
                    setLatitude(null)
                    setLatError(null)
                  } else {
                    const num = parseFloat(value)
                    if (!isNaN(num) && num >= -90 && num <= 90) {
                      setLatitude(num)
                      setLatError(null)
                    } else {
                      setLatError("Latitude must be between -90 and 90")
                    }
                  }
                }}
                placeholder="e.g., 40.7128"
                className="bg-background/50 border-borderColor/50 focus:border-primary/50"
              />
              {latError && (
                <p className="text-xs text-red-400 mt-1">{latError}</p>
              )}
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
                  if (value === "") {
                    setLongitude(null)
                    setLngError(null)
                  } else {
                    const num = parseFloat(value)
                    if (!isNaN(num) && num >= -180 && num <= 180) {
                      setLongitude(num)
                      setLngError(null)
                    } else {
                      setLngError("Longitude must be between -180 and 180")
                    }
                  }
                }}
                placeholder="e.g., -74.0060"
                className="bg-background/50 border-borderColor/50 focus:border-primary/50"
              />
              {lngError && (
                <p className="text-xs text-red-400 mt-1">{lngError}</p>
              )}
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
                Automatically record weather conditions during image captures. Weather data is collected in the background and saved with each image.
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
        </div>

        <Separator />

        {/* Sunrise/Sunset Time Windows */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <Label className="text-sm font-medium">Sunrise/Sunset Time Windows</Label>
              <p className="text-xs text-muted-foreground">
                Enable sunrise and sunset time windows for timelapse configuration. Sun times are calculated automatically based on your location and date. Specific offsets are configured per-timelapse.
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
        </div>
      </CardContent>
    </Card>
  )
}
