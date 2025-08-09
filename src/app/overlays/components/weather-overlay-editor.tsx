// src/app/overlays/components/weather-overlay-editor.tsx
"use client"

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { Cloud, Loader2, AlertTriangle, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"
import type { OverlayItem } from "@/hooks/use-overlay-presets"
import { useWeatherData } from "@/hooks/use-weather-data"

interface WeatherOverlayEditorProps {
  overlay: OverlayItem
  onUpdateOverlay: (overlay: OverlayItem) => void
}

export function WeatherOverlayEditor({
  overlay,
  onUpdateOverlay,
}: WeatherOverlayEditorProps) {
  const { weatherData, loading, error, refetch } = useWeatherData()

  const updateOverlaySetting = (key: string, value: any) => {
    const updatedOverlay = {
      ...overlay,
      settings: { ...overlay.settings, [key]: value },
    }
    onUpdateOverlay(updatedOverlay)
  }

  // Helper function to format temperature based on unit
  const formatTemperature = (temp: number | null | undefined, unit: string) => {
    if (temp === null || temp === undefined) return "N/A"

    if (unit === "Fahrenheit") {
      // Convert Celsius to Fahrenheit if needed (assuming backend stores in Celsius)
      const fahrenheit = (temp * 9) / 5 + 32
      return `${Math.round(fahrenheit)}°F`
    }
    return `${Math.round(temp)}°C`
  }

  // Helper function to get display preview
  const getDisplayPreview = () => {
    const unit = overlay.settings?.unit || "Celsius"
    const display = overlay.settings?.display || "both"
    const temp = weatherData?.current_temp
    const condition = weatherData?.current_weather_description || "Unknown"

    switch (display) {
      case "temp_only":
        return formatTemperature(temp, unit)
      case "conditions_only":
        return condition.charAt(0).toUpperCase() + condition.slice(1)
      case "both":
        return `${formatTemperature(temp, unit)} ${
          condition.charAt(0).toUpperCase() + condition.slice(1)
        }`
      default:
        return "N/A"
    }
  }

  return (
    <div className='space-y-4'>
      <div className='flex items-center gap-2 mb-3'>
        <Cloud className='w-4 h-4 text-purple' />
        <Label className='text-white text-sm font-medium'>
          Weather Overlay
        </Label>
      </div>

      {/* Live Weather Preview */}
      <div className='space-y-2'>
        <Label className='text-white text-xs font-medium'>Live Preview</Label>
        <div className='p-3 bg-gray-800/50 border border-gray-600/50 rounded text-white text-sm font-mono flex items-center justify-between'>
          {loading ? (
            <div className='flex items-center gap-2'>
              <Loader2 className='w-4 h-4 animate-spin text-cyan' />
              <span>Loading weather data...</span>
            </div>
          ) : error ? (
            <div className='flex items-center gap-2'>
              <AlertTriangle className='w-4 h-4 text-orange-400' />
              <span className='text-orange-400'>No weather data available</span>
            </div>
          ) : weatherData ? (
            <div className='flex items-center gap-2'>
              <Cloud className='w-4 h-4 text-cyan' />
              <span>{getDisplayPreview()}</span>
            </div>
          ) : (
            <span className='text-gray-400'>Weather data not configured</span>
          )}

          <Button
            size='sm'
            variant='ghost'
            onClick={refetch}
            disabled={loading}
            className='h-6 w-6 p-0 hover:bg-cyan/20'
          >
            <RefreshCw
              className={cn("w-3 h-3 text-cyan", loading && "animate-spin")}
            />
          </Button>
        </div>
      </div>

      {/* Unit Selection */}
      <div className='space-y-2'>
        <Label className='text-white text-xs font-medium'>
          Temperature Unit
        </Label>
        <div className='flex gap-2'>
          <Button
            variant={
              overlay.settings?.unit === "Fahrenheit" ? "default" : "outline"
            }
            className={cn(
              "text-xs h-8 flex-1",
              overlay.settings?.unit === "Fahrenheit"
                ? "bg-purple/30 text-white border-purple/50"
                : "border-gray-500 text-gray-400 hover:bg-gray-700/50"
            )}
            onClick={() => updateOverlaySetting("unit", "Fahrenheit")}
          >
            Fahrenheit (°F)
          </Button>
          <Button
            variant={
              overlay.settings?.unit === "Celsius" ? "default" : "outline"
            }
            className={cn(
              "text-xs h-8 flex-1",
              overlay.settings?.unit === "Celsius"
                ? "bg-purple/30 text-white border-purple/50"
                : "border-gray-500 text-gray-400 hover:bg-gray-700/50"
            )}
            onClick={() => updateOverlaySetting("unit", "Celsius")}
          >
            Celsius (°C)
          </Button>
        </div>
      </div>

      {/* Display Options */}
      <div className='space-y-2'>
        <Label className='text-white text-xs font-medium'>Display Mode</Label>
        <div className='space-y-1'>
          {[
            {
              key: "temp_only",
              label: "Temperature Only",
              getExample: () =>
                formatTemperature(
                  weatherData?.current_temp,
                  overlay.settings?.unit || "Celsius"
                ),
            },
            {
              key: "conditions_only",
              label: "Conditions Only",
              getExample: () =>
                weatherData?.current_weather_description
                  ? weatherData.current_weather_description
                      .charAt(0)
                      .toUpperCase() +
                    weatherData.current_weather_description.slice(1)
                  : "Sunny",
            },
            {
              key: "both",
              label: "Temp + Conditions",
              getExample: () => {
                const temp = formatTemperature(
                  weatherData?.current_temp,
                  overlay.settings?.unit || "Celsius"
                )
                const condition = weatherData?.current_weather_description
                  ? weatherData.current_weather_description
                      .charAt(0)
                      .toUpperCase() +
                    weatherData.current_weather_description.slice(1)
                  : "Sunny"
                return `${temp} ${condition}`
              },
            },
          ].map((option) => (
            <Button
              key={option.key}
              variant={
                overlay.settings?.display === option.key ? "default" : "outline"
              }
              className={cn(
                "w-full text-xs h-8 justify-between",
                overlay.settings?.display === option.key
                  ? "bg-purple/30 text-white border-purple/50"
                  : "border-gray-500 text-gray-400 hover:bg-gray-700/50"
              )}
              onClick={() => updateOverlaySetting("display", option.key)}
            >
              <span>{option.label}</span>
              <span className='text-cyan/70 font-mono'>
                {option.getExample()}
              </span>
            </Button>
          ))}
        </div>
      </div>

      {/* Weather Data Source Info */}
      <div className='p-3 bg-cyan/5 border border-cyan/20 rounded-lg'>
        <div className='flex items-center gap-2 mb-2'>
          <Cloud className='w-4 h-4 text-cyan' />
          <Label className='text-cyan text-xs font-medium'>
            Cached Weather Data
          </Label>
        </div>
        <p className='text-xs text-gray-400 leading-relaxed mb-2'>
          Weather data is automatically fetched hourly from OpenWeather API and
          cached in the database. No live API calls are made during overlay
          preview - data comes from the cached database records.
        </p>
        {weatherData && weatherData.weather_date_fetched && (
          <div className='text-xs text-cyan/70'>
            <div>
              Last updated:{" "}
              {new Date(weatherData.weather_date_fetched).toLocaleString()}
            </div>
            <div className='font-mono mt-1'>Current: {getDisplayPreview()}</div>
          </div>
        )}
        {!weatherData && !loading && (
          <div className='text-xs text-orange-400'>
            Configure weather integration in Settings → Weather to enable live
            data.
          </div>
        )}
      </div>

      {/* Common Overlay Settings */}
      <div className='space-y-3 pt-3 border-t border-gray-600/30'>
        {/* Font Size */}
        <div className='space-y-2'>
          <Label className='text-white text-xs font-medium'>Font Size</Label>
          <div className='flex items-center gap-2'>
            <Slider
              value={[overlay.settings?.textSize || 16]}
              onValueChange={(value) =>
                updateOverlaySetting("textSize", value[0])
              }
              max={72}
              min={8}
              step={1}
              className='flex-1'
            />
            <span className='text-white text-xs w-8 text-right'>
              {overlay.settings?.textSize || 16}px
            </span>
          </div>
        </div>

        {/* Enable Background */}
        <div className='flex items-center justify-between'>
          <Label className='text-white text-xs font-medium'>
            Enable Background
          </Label>
          <Switch
            checked={overlay.settings?.enableBackground || false}
            onCheckedChange={(checked) =>
              updateOverlaySetting("enableBackground", checked)
            }
            colorTheme='cyan'
          />
        </div>
      </div>
    </div>
  )
}
