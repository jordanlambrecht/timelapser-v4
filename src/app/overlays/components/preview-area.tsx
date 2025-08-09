// src/app/overlays/components/preview-area.tsx
"use client"

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Camera,
  DownloadCloud,
  Cloud,
  Download,
  Plus,
  X,
  Loader2,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { GRID_POSITIONS, getPositionStyles } from "./overlay-constants"
import type { OverlayItem, GlobalSettings } from "@/hooks/use-overlay-presets"
import { useWeatherData } from "@/hooks/use-weather-data"
import { formatDateTime } from "@/utils/date-format-utils"

interface PreviewAreaProps {
  imageUrl: string
  isGrabbingFrame: boolean
  overlayItems: OverlayItem[]
  globalSettings: GlobalSettings
  overlaysEnabled: boolean
  showGrid: boolean
  showMargins: boolean
  selectedPosition: string | null
  selectedCameraId: number
  cameras: Array<{ id: number; name: string }>
  onGrabFreshFrame: () => void
  onGridClick: (position: string) => void
  onRemoveOverlay: (position: string) => void
  onCameraChange: (cameraId: string) => void
  onOverlaysEnabledChange: (enabled: boolean) => void
  onShowGridChange: (show: boolean) => void
  onShowMarginsChange: (show: boolean) => void
  onExport: () => void
}

export function PreviewArea({
  imageUrl,
  isGrabbingFrame,
  overlayItems,
  globalSettings,
  overlaysEnabled,
  showGrid,
  showMargins,
  selectedPosition,
  selectedCameraId,
  cameras,
  onGrabFreshFrame,
  onGridClick,
  onRemoveOverlay,
  onCameraChange,
  onOverlaysEnabledChange,
  onShowGridChange,
  onShowMarginsChange,
  onExport,
}: PreviewAreaProps) {
  const { weatherData } = useWeatherData()

  const getOverlayAtPosition = (position: string) => {
    return overlayItems.find((item) => item.position === position)
  }

  const formatTemperature = (temp: number, unit: string = "fahrenheit") => {
    return unit === "celsius"
      ? `${Math.round(((temp - 32) * 5) / 9)}°C`
      : `${Math.round(temp)}°F`
  }

  const getWeatherDisplay = (weatherItem: any) => {
    if (!weatherData) {
      return "Loading..."
    }

    const settings = weatherItem.settings || {}
    const displayMode = settings.displayMode || "both"
    const tempUnit = settings.temperatureUnit || "fahrenheit"

    const temp = weatherData.current_temp
      ? formatTemperature(weatherData.current_temp, tempUnit)
      : "N/A"
    const condition = weatherData.current_weather_description || "Clear"

    switch (displayMode) {
      case "temperature_only":
        return temp
      case "conditions_only":
        return condition
      case "both":
      default:
        return `${temp} ${condition}`
    }
  }

  return (
    <div className='space-y-4'>
      {/* Header Controls */}
      <div className='flex items-center justify-between'>
        <div className='flex items-center gap-4'>
          <div className='flex items-center gap-2'>
            <Camera className='w-5 h-5 text-cyan' />
            <h3 className='text-lg font-semibold text-white'>Live Preview</h3>
          </div>

          {/* Camera Selection Dropdown */}
          <Select
            value={selectedCameraId.toString()}
            onValueChange={onCameraChange}
          >
            <SelectTrigger className='w-48 bg-gray-800/50 border-gray-600/50 text-white'>
              <SelectValue placeholder='Select camera...' />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value='placeholder'>Placeholder Preview</SelectItem>
              {cameras.map((camera) => (
                <SelectItem key={camera.id} value={camera.id.toString()}>
                  {camera.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Button
          onClick={onGrabFreshFrame}
          disabled={isGrabbingFrame}
          className='bg-red-500/80 hover:bg-red-500 text-white border-0'
        >
          {isGrabbingFrame ? (
            <>
              <Loader2 className='w-4 h-4 mr-2 animate-spin' />
              Capturing...
            </>
          ) : (
            <>
              <DownloadCloud className='w-4 h-4 mr-2' />
              Grab Fresh Frame
            </>
          )}
        </Button>
      </div>

      {/* Image Preview with Interactive Grid */}
      <div className='relative bg-black/20 border border-cyan/20 rounded-xl overflow-hidden aspect-video'>
        {imageUrl ? (
          <div className='relative w-full h-full'>
            <img
              src={imageUrl}
              alt='Camera preview'
              className='w-full h-full object-cover'
            />

            {/* Interactive Overlay Grid */}
            <div className='absolute inset-0'>
              <div className='grid grid-cols-3 grid-rows-3 w-full h-full'>
                {GRID_POSITIONS.map((gridPos) => {
                  const overlay = getOverlayAtPosition(gridPos.id)
                  const isSelected = selectedPosition === gridPos.id

                  return (
                    <div
                      key={gridPos.id}
                      className={cn(
                        "border border-transparent hover:border-cyan/50 hover:bg-cyan/10 cursor-pointer transition-all",
                        "flex items-center justify-center relative group",
                        isSelected && "border-purple/70 bg-purple/10",
                        overlay && "border-green/50 bg-green/10"
                      )}
                      onClick={() => onGridClick(gridPos.id)}
                    >
                      {/* Grid Position Indicator */}
                      <div
                        className={cn(
                          "absolute inset-2 border-2 border-dashed border-white/20 rounded-lg",
                          "group-hover:border-cyan/50 transition-all",
                          isSelected && "border-purple/70",
                          overlay && "border-green/50"
                        )}
                      >
                        {overlay ? (
                          // Show overlay preview with remove button on hover
                          <div className='absolute inset-0 flex items-center justify-center'>
                            <div className='bg-black/70 text-white px-2 py-1 rounded text-xs'>
                              {overlay.type.replace("_", " ")}
                            </div>
                            {/* Remove button - show on hover */}
                            <button
                              className='absolute -top-2 -right-2 bg-red-500 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity'
                              onClick={(e) => {
                                e.stopPropagation()
                                onRemoveOverlay(gridPos.id)
                              }}
                            >
                              <X className='w-3 h-3' />
                            </button>
                          </div>
                        ) : (
                          // Show add button on hover
                          <div className='absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity'>
                            <div className='bg-cyan/80 text-white p-2 rounded-full'>
                              <Plus className='w-4 h-4' />
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Grid Overlay */}
            {showGrid && (
              <div className='absolute inset-0 pointer-events-none'>
                <div className='absolute inset-0'>
                  {/* 3x3 grid */}
                  <div className='absolute left-1/3 top-0 bottom-0 w-px bg-cyan/50'></div>
                  <div className='absolute left-2/3 top-0 bottom-0 w-px bg-cyan/50'></div>
                  <div className='absolute top-1/3 left-0 right-0 h-px bg-cyan/50'></div>
                  <div className='absolute top-2/3 left-0 right-0 h-px bg-cyan/50'></div>
                </div>
              </div>
            )}

            {/* Margins Overlay */}
            {showMargins && (
              <div className='absolute inset-0 pointer-events-none'>
                <div
                  className='absolute border border-purple/50 border-dashed'
                  style={{
                    top: `${globalSettings.yMargin}px`,
                    left: `${globalSettings.xMargin}px`,
                    right: `${globalSettings.xMargin}px`,
                    bottom: `${globalSettings.yMargin}px`,
                  }}
                ></div>
              </div>
            )}

            {/* Actual Overlay Previews */}
            {overlaysEnabled &&
              overlayItems.map((item) => {
                if (!item.enabled) return null

                const style = {
                  opacity: globalSettings.opacity / 100,
                  filter: `drop-shadow(0 2px ${
                    globalSettings.dropShadow / 10
                  }px rgba(0,0,0,0.5))`,
                }

                const backgroundStyle = {
                  backgroundColor: `${
                    globalSettings.backgroundColor
                  }${Math.round((globalSettings.backgroundOpacity / 100) * 255)
                    .toString(16)
                    .padStart(2, "0")}`,
                }

                return (
                  <div
                    key={item.id}
                    className={cn(
                      "absolute backdrop-blur-sm rounded-lg p-2 border border-white/20 pointer-events-none",
                      getPositionStyles(item.position)
                    )}
                    style={{ ...style, ...backgroundStyle }}
                  >
                    <div className='text-white text-sm font-medium flex items-center gap-2'>
                      {item.type === "weather" && (
                        <>
                          <Cloud className='w-4 h-4' />
                          {getWeatherDisplay(item)}
                        </>
                      )}
                      {item.type === "date_time" &&
                        formatDateTime(
                          item.settings?.format || "MM/DD/YYYY HH:mm"
                        )}
                      {item.type === "frame_number" && "#1,247"}
                      {item.type === "custom_text" &&
                        (item.settings?.customText || "Custom Text")}
                      {item.type === "timelapse_name" && "Sample Timelapse"}
                      {item.type === "day_number" && "Day 45"}
                    </div>
                  </div>
                )
              })}
          </div>
        ) : (
          <div className='flex items-center justify-center w-full h-full text-gray-500'>
            <div className='text-center'>
              <Camera className='w-16 h-16 mx-auto text-gray-400 mb-4' />
              <p className='text-lg font-medium'>Loading preview...</p>
            </div>
          </div>
        )}
      </div>

      {/* Bottom Controls */}
      <div className='flex items-center justify-between'>
        <div className='flex items-center gap-6'>
          {/* Overlays Toggle */}
          <div className='flex items-center gap-3'>
            <Label className='text-white text-sm font-medium'>Overlays</Label>
            <div className='flex items-center'>
              <span
                className={cn(
                  "text-xs mr-2",
                  overlaysEnabled ? "text-gray-400" : "text-white"
                )}
              >
                OFF
              </span>
              <Switch
                checked={overlaysEnabled}
                onCheckedChange={onOverlaysEnabledChange}
                colorTheme='pink'
              />
              <span
                className={cn(
                  "text-xs ml-2",
                  overlaysEnabled ? "text-white" : "text-gray-400"
                )}
              >
                ON
              </span>
            </div>
          </div>

          {/* Show Grid Toggle */}
          <div className='flex items-center gap-3'>
            <Label className='text-white text-sm font-medium'>Show Grid</Label>
            <Switch
              checked={showGrid}
              onCheckedChange={onShowGridChange}
              colorTheme='cyan'
            />
          </div>

          {/* Show Margins Toggle */}
          <div className='flex items-center gap-3'>
            <Label className='text-white text-sm font-medium'>
              Show Margins
            </Label>
            <Switch
              checked={showMargins}
              onCheckedChange={onShowMarginsChange}
              colorTheme='cyan'
            />
          </div>
        </div>

        {/* Export Button */}
        <Button
          onClick={onExport}
          variant='outline'
          className='border-cyan/30 text-white hover:bg-cyan/20'
        >
          <Download className='w-4 h-4 mr-2' />
          Export Config
        </Button>
      </div>
    </div>
  )
}
