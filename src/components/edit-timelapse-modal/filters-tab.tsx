// src/components/edit-timelapse-modal/filters-tab.tsx
"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
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
  Filter,
  Sun,
  Contrast,
  Palette,
  Droplets,
  RotateCcw,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "@/lib/toast"

interface FiltersTabProps {
  timelapse: {
    id: number
    name: string
    status: string
    image_count: number
    start_date: string
    last_capture_at?: string
  }
  cameraId: number
  cameraName: string
  onDataChange?: () => void
}

interface FilterSettings {
  brightness: number
  contrast: number
  saturation: number
  hue: number
  colorFilter: string
  enabled: boolean
}

export function FiltersTab({
  timelapse,
  cameraId,
  cameraName,
  onDataChange,
}: FiltersTabProps) {
  const [imageUrl, setImageUrl] = useState<string>("")
  const [isGrabbingFrame, setIsGrabbingFrame] = useState(false)

  const [filterSettings, setFilterSettings] = useState<FilterSettings>({
    brightness: 100,
    contrast: 100,
    saturation: 100,
    hue: 0,
    colorFilter: "none",
    enabled: true,
  })

  // Initialize image URL
  useEffect(() => {
    setImageUrl(`/api/cameras/${cameraId}/latest-image/small?t=${Date.now()}`)
  }, [cameraId])

  const handleGrabFreshFrame = async () => {
    setIsGrabbingFrame(true)
    try {
      const response = await fetch(`/api/overlays/fresh-photo/${cameraId}`, {
        method: "POST",
      })

      if (!response.ok) {
        // If fresh capture fails, fall back to refreshing the latest image
        console.warn(
          "Fresh capture failed, falling back to latest image refresh"
        )
        setImageUrl(
          `/api/cameras/${cameraId}/latest-image/small?t=${Date.now()}`
        )
        toast.success("Image refreshed!")
        return
      }

      setTimeout(() => {
        setImageUrl(
          `/api/cameras/${cameraId}/latest-image/small?t=${Date.now()}`
        )
        toast.success("Fresh frame captured!")
      }, 2000)
    } catch (error) {
      console.error("Failed to grab fresh frame:", error)
      // Fall back to refreshing the latest image
      setImageUrl(`/api/cameras/${cameraId}/latest-image/small?t=${Date.now()}`)
      toast.error("Fresh capture failed, refreshed latest image instead")
    } finally {
      setIsGrabbingFrame(false)
    }
  }

  const updateFilterSetting = (key: keyof FilterSettings, value: any) => {
    setFilterSettings((prev) => ({ ...prev, [key]: value }))
    onDataChange?.()
  }

  const resetFilters = () => {
    setFilterSettings({
      brightness: 100,
      contrast: 100,
      saturation: 100,
      hue: 0,
      colorFilter: "none",
      enabled: true,
    })
    onDataChange?.()
  }

  // Generate CSS filter string
  const getFilterCSS = () => {
    if (!filterSettings.enabled) return "none"

    const filters = []

    if (filterSettings.brightness !== 100) {
      filters.push(`brightness(${filterSettings.brightness}%)`)
    }
    if (filterSettings.contrast !== 100) {
      filters.push(`contrast(${filterSettings.contrast}%)`)
    }
    if (filterSettings.saturation !== 100) {
      filters.push(`saturate(${filterSettings.saturation}%)`)
    }
    if (filterSettings.hue !== 0) {
      filters.push(`hue-rotate(${filterSettings.hue}deg)`)
    }

    // Color filter presets
    switch (filterSettings.colorFilter) {
      case "sepia":
        filters.push("sepia(100%)")
        break
      case "grayscale":
        filters.push("grayscale(100%)")
        break
      case "vintage":
        filters.push("sepia(50%) contrast(110%) brightness(110%)")
        break
      case "cool":
        filters.push("hue-rotate(180deg) saturate(120%)")
        break
      case "warm":
        filters.push("hue-rotate(-20deg) saturate(120%) brightness(105%)")
        break
    }

    return filters.length > 0 ? filters.join(" ") : "none"
  }

  const colorFilterOptions = [
    { value: "none", label: "None" },
    { value: "sepia", label: "Sepia" },
    { value: "grayscale", label: "Grayscale" },
    { value: "vintage", label: "Vintage" },
    { value: "cool", label: "Cool Tone" },
    { value: "warm", label: "Warm Tone" },
  ]

  return (
    <div className='grid grid-cols-1 lg:grid-cols-4 gap-6 h-full'>
      {/* Left Column - Preview */}
      <div className='lg:col-span-3 space-y-4'>
        <div className='flex items-center justify-between'>
          <div className='flex items-center gap-2'>
            <Camera className='w-5 h-5 text-cyan' />
            <h3 className='text-lg font-semibold text-white'>Filter Preview</h3>
          </div>
          <div className='flex items-center gap-2'>
            <Button
              onClick={handleGrabFreshFrame}
              disabled={isGrabbingFrame}
              size='sm'
              className='bg-black/60 hover:bg-black/80 text-white border border-cyan/30'
            >
              {isGrabbingFrame ? (
                <>
                  <div className='w-4 h-4 mr-2 border-2 border-white border-t-transparent rounded-full animate-spin' />
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
        </div>

        {/* Image Preview with Filters */}
        <div className='relative bg-black/20 border border-cyan/20 rounded-xl overflow-hidden aspect-video'>
          {imageUrl ? (
            <div className='relative w-full h-full'>
              <img
                src={imageUrl}
                alt='Camera preview'
                className='w-full h-full object-cover transition-all duration-300'
                style={{
                  filter: getFilterCSS(),
                }}
              />

              {/* Filter overlay indicator */}
              {filterSettings.enabled && getFilterCSS() !== "none" && (
                <div className='absolute top-4 left-4 bg-black/60 backdrop-blur-sm rounded-lg p-2 border border-white/20'>
                  <div className='text-white text-xs font-medium'>
                    Filters Applied
                  </div>
                </div>
              )}
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

        {/* Filter Enable Toggle */}
        <div className='flex items-center justify-between'>
          <div className='flex items-center gap-3'>
            <Label className='text-white font-medium'>Enable Filters</Label>
            <Switch
              checked={filterSettings.enabled}
              onCheckedChange={(checked) =>
                updateFilterSetting("enabled", checked)
              }
              colorTheme='cyan'
            />
          </div>

          <Button
            onClick={resetFilters}
            size='sm'
            variant='outline'
            className='border-purple/30 text-purple hover:bg-purple/20'
          >
            <RotateCcw className='w-4 h-4 mr-2' />
            Reset
          </Button>
        </div>
      </div>

      {/* Right Column - Filter Controls */}
      <div className='space-y-6'>
        {/* Color Filter Presets */}
        <div className='space-y-3'>
          <div className='flex items-center gap-2'>
            <Palette className='w-4 h-4 text-purple' />
            <Label className='text-white font-medium'>Color Filter</Label>
          </div>
          <Select
            value={filterSettings.colorFilter}
            onValueChange={(value) => updateFilterSetting("colorFilter", value)}
            disabled={!filterSettings.enabled}
          >
            <SelectTrigger className='bg-black/20 border-purple/30 text-white'>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {colorFilterOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Brightness */}
        <div className='space-y-3'>
          <div className='flex items-center gap-2'>
            <Sun className='w-4 h-4 text-yellow' />
            <Label className='text-white font-medium'>Brightness</Label>
          </div>
          <div className='p-4 bg-yellow/5 border border-yellow/20 rounded-lg space-y-3'>
            <Slider
              value={[filterSettings.brightness]}
              onValueChange={(value) =>
                updateFilterSetting("brightness", value[0])
              }
              min={0}
              max={200}
              step={5}
              disabled={!filterSettings.enabled}
              className='w-full'
            />
            <div className='text-center text-yellow text-sm font-mono'>
              {filterSettings.brightness}%
            </div>
          </div>
        </div>

        {/* Contrast */}
        <div className='space-y-3'>
          <div className='flex items-center gap-2'>
            <Contrast className='w-4 h-4 text-cyan' />
            <Label className='text-white font-medium'>Contrast</Label>
          </div>
          <div className='p-4 bg-cyan/5 border border-cyan/20 rounded-lg space-y-3'>
            <Slider
              value={[filterSettings.contrast]}
              onValueChange={(value) =>
                updateFilterSetting("contrast", value[0])
              }
              min={0}
              max={200}
              step={5}
              disabled={!filterSettings.enabled}
              className='w-full'
            />
            <div className='text-center text-cyan text-sm font-mono'>
              {filterSettings.contrast}%
            </div>
          </div>
        </div>

        {/* Saturation */}
        <div className='space-y-3'>
          <div className='flex items-center gap-2'>
            <Droplets className='w-4 h-4 text-green-400' />
            <Label className='text-white font-medium'>Saturation</Label>
          </div>
          <div className='p-4 bg-green-500/5 border border-green-500/20 rounded-lg space-y-3'>
            <Slider
              value={[filterSettings.saturation]}
              onValueChange={(value) =>
                updateFilterSetting("saturation", value[0])
              }
              min={0}
              max={200}
              step={5}
              disabled={!filterSettings.enabled}
              className='w-full'
            />
            <div className='text-center text-green-400 text-sm font-mono'>
              {filterSettings.saturation}%
            </div>
          </div>
        </div>

        {/* Hue */}
        <div className='space-y-3'>
          <div className='flex items-center gap-2'>
            <Filter className='w-4 h-4 text-purple' />
            <Label className='text-white font-medium'>Hue Shift</Label>
          </div>
          <div className='p-4 bg-purple/5 border border-purple/20 rounded-lg space-y-3'>
            <Slider
              value={[filterSettings.hue]}
              onValueChange={(value) => updateFilterSetting("hue", value[0])}
              min={-180}
              max={180}
              step={5}
              disabled={!filterSettings.enabled}
              className='w-full'
            />
            <div className='text-center text-purple text-sm font-mono'>
              {filterSettings.hue}°
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
