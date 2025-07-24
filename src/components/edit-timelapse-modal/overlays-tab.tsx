// src/components/edit-timelapse-modal/overlays-tab.tsx
"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { Input } from "@/components/ui/input"
import {
  Camera,
  DownloadCloud,
  ChevronRight,
  Globe,
  Cloud,
  Image as ImageIcon,
  Hash,
  Calendar,
  Thermometer,
  Type,
  FileText,
  Eye,
  EyeOff,
  Download,
  Plus,
  Settings as SettingsIcon,
  Grid3x3,
  Move,
  X,
  ChevronDown,
  Upload,
  Margins,
  Activity,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "@/lib/toast"
import { useOverlayPresets } from "@/hooks/use-overlay-presets"
import { AddOverlayModal } from "./add-overlay-modal"
import { DateTimeFormatBuilder } from "./date-time-format-builder"
import { formatDateTime } from "@/utils/date-format-utils"

interface OverlaysTabProps {
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

interface OverlayItem {
  id: string
  name: string
  type: "weather" | "watermark" | "frame_number" | "date_time" | "day_counter" | "custom_text" | "timelapse_name"
  enabled: boolean
  position: string
  icon: any
  color: string
  settings?: any
}

interface GlobalSettings {
  opacity: number
  font: string
  xMargin: number
  yMargin: number
  backgroundColor: string
  backgroundOpacity: number
  fillColor: string
  dropShadow: number
  preset?: string
}

interface WeatherSettings {
  unit: "Celsius" | "Fahrenheit"
  display: "temp_only" | "conditions_only" | "both"
  textSize: number
  enableBackground: boolean
  enabled: boolean
}

interface WatermarkSettings {
  imageFile?: File
  imageScale: number
  imageUrl?: string
}

interface FrameNumberSettings {
  textSize: number
  leadingZeros: boolean
  enableBackground: boolean
  enabled: boolean
}

interface DateTimeSettings {
  dateFormat: string
  textSize: number
  enableBackground: boolean
  enabled: boolean
}

interface CustomTextSettings {
  customText: string
  textSize: number
  enableBackground: boolean
  enabled: boolean
}

interface TimelapseNameSettings {
  textSize: number
  enableBackground: boolean
  enabled: boolean
}

interface DayCounterSettings {
  leadingZeros: boolean
  textSize: number
  hidePrefix: boolean
  enableBackground: boolean
  enabled: boolean
}

export function OverlaysTab({
  timelapse,
  cameraId,
  cameraName,
  onDataChange,
}: OverlaysTabProps) {
  const [imageUrl, setImageUrl] = useState<string>("")
  const [isGrabbingFrame, setIsGrabbingFrame] = useState(false)
  const [overlaysEnabled, setOverlaysEnabled] = useState(true)
  const [liveViewEnabled, setLiveViewEnabled] = useState(true)
  const [showGrid, setShowGrid] = useState(false)
  const [showMargins, setShowMargins] = useState(false)
  const [globalsExpanded, setGlobalsExpanded] = useState(true)
  const [selectedOverlay, setSelectedOverlay] = useState<string | null>(null)
  const [showAddModal, setShowAddModal] = useState(false)
  
  const { presets, loading, fetchPresets } = useOverlayPresets()
  
  // Global settings state
  const [globalSettings, setGlobalSettings] = useState<GlobalSettings>({
    opacity: 90,
    font: "Helvetica",
    xMargin: 15,
    yMargin: 15,
    backgroundColor: "#000000",
    backgroundOpacity: 50,
    fillColor: "#FFFFFF",
    dropShadow: 50,
    preset: "Weather Tracking"
  })

  // Sample overlay items - in real implementation this would come from API
  const [overlayItems, setOverlayItems] = useState<OverlayItem[]>([
    {
      id: "weather",
      name: "Weather Overlay",
      type: "weather",
      enabled: true,
      position: "topLeft",
      icon: Cloud,
      color: "text-purple",
      settings: {
        unit: "Celsius",
        display: "both",
        textSize: 16,
        enableBackground: true,
        enabled: true
      }
    },
    {
      id: "watermark",
      name: "Watermark Overlay",
      type: "watermark",
      enabled: false,
      position: "bottomRight",
      icon: ImageIcon,
      color: "text-cyan",
      settings: {
        imageScale: 100,
        imageUrl: ""
      }
    },
    {
      id: "frame_number",
      name: "Frame Number",
      type: "frame_number",
      enabled: false,
      position: "bottomLeft",
      icon: Hash,
      color: "text-pink",
      settings: {
        textSize: 16,
        leadingZeros: false,
        enableBackground: false,
        enabled: false
      }
    },
    {
      id: "date_time",
      name: "Date & Time",
      type: "date_time",
      enabled: false,
      position: "topRight",
      icon: Calendar,
      color: "text-cyan",
      settings: {
        dateFormat: "MM/dd/yyyy HH:mm",
        textSize: 16,
        enableBackground: false,
        enabled: false
      }
    },
  ])

  // Initialize image URL
  useEffect(() => {
    setImageUrl(`/api/cameras/${cameraId}/latest-image/small?t=${Date.now()}`)
  }, [cameraId])

  // Fetch overlay presets
  useEffect(() => {
    fetchPresets()
  }, [])

  const handleGrabFreshFrame = async () => {
    setIsGrabbingFrame(true)
    try {
      const response = await fetch(`/api/cameras/${cameraId}/capture-now`, {
        method: "POST",
      })

      if (!response.ok) {
        throw new Error("Failed to capture fresh frame")
      }

      setTimeout(() => {
        setImageUrl(`/api/cameras/${cameraId}/latest-image/small?t=${Date.now()}`)
        toast.success("Fresh frame captured!")
      }, 2000)
      
    } catch (error) {
      console.error("Failed to grab fresh frame:", error)
      toast.error("Failed to capture fresh frame")
    } finally {
      setIsGrabbingFrame(false)
    }
  }

  const toggleOverlayItem = (id: string) => {
    setOverlayItems(prev => prev.map(item => 
      item.id === id ? { ...item, enabled: !item.enabled } : item
    ))
    onDataChange?.()
  }

  const handleAddOverlay = (overlayType: string) => {
    const overlayTypeMap: Record<string, { name: string; icon: any; color: string }> = {
      weather: { name: "Weather Overlay", icon: Cloud, color: "text-purple" },
      watermark: { name: "Watermark Overlay", icon: ImageIcon, color: "text-cyan" },
      frame_number: { name: "Frame Number", icon: Hash, color: "text-pink" },
      date_time: { name: "Date & Time", icon: Calendar, color: "text-cyan" },
      day_counter: { name: "Day Counter", icon: Activity, color: "text-purple" },
      custom_text: { name: "Custom Text", icon: Type, color: "text-pink" },
      timelapse_name: { name: "Timelapse Name", icon: FileText, color: "text-cyan" },
    }

    const config = overlayTypeMap[overlayType]
    if (!config) return

    // Default settings for each overlay type
    const getDefaultSettings = (type: string) => {
      switch (type) {
        case "weather":
          return { unit: "Celsius", display: "both", textSize: 16, enableBackground: false, enabled: true }
        case "watermark":
          return { imageScale: 100, imageUrl: "" }
        case "frame_number":
          return { textSize: 16, leadingZeros: false, enableBackground: false, enabled: true }
        case "date_time":
          return { dateFormat: "YYYY-MM-DD HH:mm:ss", textSize: 16, enableBackground: false, enabled: true }
        case "day_counter":
          return { leadingZeros: false, textSize: 16, hidePrefix: false, enableBackground: false, enabled: true }
        case "custom_text":
          return { customText: "Custom Text", textSize: 16, enableBackground: false, enabled: true }
        case "timelapse_name":
          return { textSize: 16, enableBackground: false, enabled: true }
        default:
          return {}
      }
    }

    const newOverlay: OverlayItem = {
      id: `${overlayType}_${Date.now()}`,
      name: config.name,
      type: overlayType as any,
      enabled: true,
      position: "topLeft",
      icon: config.icon,
      color: config.color,
      settings: getDefaultSettings(overlayType)
    }

    setOverlayItems(prev => [...prev, newOverlay])
    setSelectedOverlay(newOverlay.id)
    onDataChange?.()
    toast.success(`${config.name} added!`)
  }

  const handleExport = async () => {
    try {
      toast.success("Overlay preview exported!")
    } catch (error) {
      toast.error("Failed to export preview")
    }
  }

  const renderOverlaySettings = (overlayId: string) => {
    const overlay = overlayItems.find(item => item.id === overlayId)
    if (!overlay) return null

    switch (overlay.type) {
      case "weather":
        return (
          <div className="space-y-3">
            <div className="flex items-center gap-2 mb-2">
              <Cloud className="w-4 h-4 text-purple" />
              <Label className="text-white text-sm font-medium">Weather Overlay</Label>
            </div>
            
            {/* Unit */}
            <div className="space-y-2">
              <Label className="text-white text-xs font-medium">Unit</Label>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant={overlay.settings?.unit === "Fahrenheit" ? "default" : "outline"}
                  className={cn(
                    "text-xs h-7",
                    overlay.settings?.unit === "Fahrenheit" 
                      ? "bg-red-500 text-white" 
                      : "border-gray-500 text-gray-400"
                  )}
                  onClick={() => {
                    setOverlayItems(prev => prev.map(item => 
                      item.id === overlayId 
                        ? { ...item, settings: { ...item.settings, unit: "Fahrenheit" } }
                        : item
                    ))
                  }}
                >
                  Fahrenheit
                </Button>
                <Button
                  size="sm"
                  variant={overlay.settings?.unit === "Celsius" ? "default" : "outline"}
                  className={cn(
                    "text-xs h-7",
                    overlay.settings?.unit === "Celsius" 
                      ? "bg-red-500 text-white" 
                      : "border-gray-500 text-gray-400"
                  )}
                  onClick={() => {
                    setOverlayItems(prev => prev.map(item => 
                      item.id === overlayId 
                        ? { ...item, settings: { ...item.settings, unit: "Celsius" } }
                        : item
                    ))
                  }}
                >
                  Celsius
                </Button>
              </div>
            </div>
            
            {/* Display */}
            <div className="space-y-2">
              <Label className="text-white text-xs font-medium">Display</Label>
              <div className="space-y-1">
                {[
                  { key: "temp_only", label: "Temperature Only" },
                  { key: "conditions_only", label: "Conditions Only" },
                  { key: "both", label: "Temp + Conditions" }
                ].map((option) => (
                  <Button
                    key={option.key}
                    size="sm"
                    variant={overlay.settings?.display === option.key ? "default" : "outline"}
                    className={cn(
                      "w-full text-xs h-7 justify-start",
                      overlay.settings?.display === option.key 
                        ? "bg-red-500 text-white" 
                        : "border-gray-500 text-gray-400"
                    )}
                    onClick={() => {
                      setOverlayItems(prev => prev.map(item => 
                        item.id === overlayId 
                          ? { ...item, settings: { ...item.settings, display: option.key } }
                          : item
                      ))
                    }}
                  >
                    {option.label}
                  </Button>
                ))}
              </div>
            </div>

            {/* Text Size */}
            <div className="space-y-2">
              <Label className="text-white text-xs font-medium">Text Size</Label>
              <div className="flex items-center gap-2">
                <Slider
                  value={[overlay.settings?.textSize || 16]}
                  onValueChange={(value) => {
                    setOverlayItems(prev => prev.map(item => 
                      item.id === overlayId 
                        ? { ...item, settings: { ...item.settings, textSize: value[0] } }
                        : item
                    ))
                  }}
                  max={72}
                  min={8}
                  step={1}
                  className="flex-1"
                />
                <span className="text-white text-xs w-8 text-right">{overlay.settings?.textSize || 16}px</span>
              </div>
            </div>

            {/* Enable Background */}
            <div className="flex items-center justify-between">
              <Label className="text-white text-xs font-medium">Enable Background</Label>
              <Switch
                checked={overlay.settings?.enableBackground || false}
                onCheckedChange={(checked) => {
                  setOverlayItems(prev => prev.map(item => 
                    item.id === overlayId 
                      ? { ...item, settings: { ...item.settings, enableBackground: checked } }
                      : item
                  ))
                }}
                colorTheme="purple"
                size="sm"
              />
            </div>
            
            {/* Enabled Toggle */}
            <div className="flex items-center justify-between pt-2 border-t border-gray-600/30">
              <Label className="text-white text-sm font-medium">Enabled</Label>
              <Switch
                checked={overlay.enabled}
                onCheckedChange={() => toggleOverlayItem(overlay.id)}
                colorTheme="purple"
              />
            </div>
          </div>
        )
        
      case "watermark":
        return (
          <div className="space-y-3">
            <div className="flex items-center gap-2 mb-2">
              <ImageIcon className="w-4 h-4 text-cyan" />
              <Label className="text-white text-sm font-medium">Watermark Overlay</Label>
            </div>
            
            {/* Image Scale */}
            <div className="space-y-2">
              <Label className="text-white text-xs font-medium">Image Scale</Label>
              <div className="flex items-center gap-2">
                <Slider
                  value={[overlay.settings?.imageScale || 100]}
                  onValueChange={(value) => {
                    setOverlayItems(prev => prev.map(item => 
                      item.id === overlayId 
                        ? { ...item, settings: { ...item.settings, imageScale: value[0] } }
                        : item
                    ))
                  }}
                  max={500}
                  min={10}
                  step={5}
                  className="flex-1"
                />
                <span className="text-white text-xs w-12 text-right">{overlay.settings?.imageScale || 100}%</span>
              </div>
            </div>
            
            {/* Upload Image */}
            <div className="space-y-2">
              <Label className="text-white text-xs font-medium">Upload Image</Label>
              <div className="border-2 border-dashed border-gray-500/50 rounded-lg p-4 text-center">
                <Upload className="w-6 h-6 mx-auto text-gray-400 mb-2" />
                <p className="text-gray-400 text-xs">Drag image here or click to upload</p>
                {overlay.settings?.imageUrl && (
                  <p className="text-cyan text-xs mt-1">Image uploaded</p>
                )}
              </div>
            </div>
          </div>
        )
        
      case "frame_number":
        return (
          <div className="space-y-3">
            <div className="flex items-center gap-2 mb-2">
              <Hash className="w-4 h-4 text-pink" />
              <Label className="text-white text-sm font-medium">Frame Number</Label>
            </div>
            
            {/* Text Size */}
            <div className="space-y-2">
              <Label className="text-white text-xs font-medium">Text Size</Label>
              <div className="flex items-center gap-2">
                <Slider
                  value={[overlay.settings?.textSize || 16]}
                  onValueChange={(value) => {
                    setOverlayItems(prev => prev.map(item =>
                      item.id === overlayId 
                        ? { ...item, settings: { ...item.settings, textSize: value[0] } }
                        : item
                    ))
                  }}
                  max={72}
                  min={8}
                  step={1}
                  className="flex-1"
                />
                <span className="text-white text-xs w-8 text-right">{overlay.settings?.textSize || 16}px</span>
              </div>
            </div>
            
            {/* Leading Zeros */}
            <div className="flex items-center justify-between">
              <Label className="text-white text-xs font-medium">Leading Zeros</Label>
              <Switch
                checked={overlay.settings?.leadingZeros || false}
                onCheckedChange={(checked) => {
                  setOverlayItems(prev => prev.map(item =>
                    item.id === overlayId 
                      ? { ...item, settings: { ...item.settings, leadingZeros: checked } }
                      : item
                  ))
                }}
                colorTheme="pink"
                size="sm"
              />
            </div>

            {/* Enable Background */}
            <div className="flex items-center justify-between">
              <Label className="text-white text-xs font-medium">Enable Background</Label>
              <Switch
                checked={overlay.settings?.enableBackground || false}
                onCheckedChange={(checked) => {
                  setOverlayItems(prev => prev.map(item => 
                    item.id === overlayId 
                      ? { ...item, settings: { ...item.settings, enableBackground: checked } }
                      : item
                  ))
                }}
                colorTheme="pink"
                size="sm"
              />
            </div>
            
            {/* Enabled Toggle */}
            <div className="flex items-center justify-between pt-2 border-t border-gray-600/30">
              <Label className="text-white text-sm font-medium">Enabled</Label>
              <Switch
                checked={overlay.enabled}
                onCheckedChange={() => toggleOverlayItem(overlay.id)}
                colorTheme="pink"
              />
            </div>
          </div>
        )
        
      case "custom_text":
        return (
          <div className="space-y-3">
            <div className="flex items-center gap-2 mb-2">
              <Type className="w-4 h-4 text-pink" />
              <Label className="text-white text-sm font-medium">Custom Text</Label>
            </div>
            
            {/* Text Input */}
            <div className="space-y-2">
              <Label className="text-white text-xs font-medium">Custom Text</Label>
              <Input
                value={overlay.settings?.customText || ""}
                onChange={(e) => {
                  setOverlayItems(prev => prev.map(item =>
                    item.id === overlayId 
                      ? { ...item, settings: { ...item.settings, customText: e.target.value } }
                      : item
                  ))
                }}
                placeholder="Enter custom text..."
                className="bg-gray-800/50 border-gray-600/50 text-white placeholder-gray-400"
              />
            </div>
            
            {/* Text Size */}
            <div className="space-y-2">
              <Label className="text-white text-xs font-medium">Text Size</Label>
              <div className="flex items-center gap-2">
                <Slider
                  value={[overlay.settings?.textSize || 16]}
                  onValueChange={(value) => {
                    setOverlayItems(prev => prev.map(item =>
                      item.id === overlayId 
                        ? { ...item, settings: { ...item.settings, textSize: value[0] } }
                        : item
                    ))
                  }}
                  max={72}
                  min={8}
                  step={1}
                  className="flex-1"
                />
                <span className="text-white text-xs w-8 text-right">{overlay.settings?.textSize || 16}px</span>
              </div>
            </div>

            {/* Enable Background */}
            <div className="flex items-center justify-between">
              <Label className="text-white text-xs font-medium">Enable Background</Label>
              <Switch
                checked={overlay.settings?.enableBackground || false}
                onCheckedChange={(checked) => {
                  setOverlayItems(prev => prev.map(item => 
                    item.id === overlayId 
                      ? { ...item, settings: { ...item.settings, enableBackground: checked } }
                      : item
                  ))
                }}
                colorTheme="pink"
                size="sm"
              />
            </div>
            
            {/* Enabled Toggle */}
            <div className="flex items-center justify-between pt-2 border-t border-gray-600/30">
              <Label className="text-white text-sm font-medium">Enabled</Label>
              <Switch
                checked={overlay.enabled}
                onCheckedChange={() => toggleOverlayItem(overlay.id)}
                colorTheme="pink"
              />
            </div>
          </div>
        )
        
      case "timelapse_name":
        return (
          <div className="space-y-3">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="w-4 h-4 text-cyan" />
              <Label className="text-white text-sm font-medium">Timelapse Name</Label>
            </div>
            
            {/* Preview */}
            <div className="space-y-2">
              <Label className="text-white text-xs font-medium">Preview</Label>
              <div className="p-2 bg-gray-800/50 border border-gray-600/50 rounded text-white text-sm">
                {timelapse.name}
              </div>
            </div>
            
            {/* Text Size */}
            <div className="space-y-2">
              <Label className="text-white text-xs font-medium">Text Size</Label>
              <div className="flex items-center gap-2">
                <Slider
                  value={[overlay.settings?.textSize || 16]}
                  onValueChange={(value) => {
                    setOverlayItems(prev => prev.map(item =>
                      item.id === overlayId 
                        ? { ...item, settings: { ...item.settings, textSize: value[0] } }
                        : item
                    ))
                  }}
                  max={72}
                  min={8}
                  step={1}
                  className="flex-1"
                />
                <span className="text-white text-xs w-8 text-right">{overlay.settings?.textSize || 16}px</span>
              </div>
            </div>

            {/* Enable Background */}
            <div className="flex items-center justify-between">
              <Label className="text-white text-xs font-medium">Enable Background</Label>
              <Switch
                checked={overlay.settings?.enableBackground || false}
                onCheckedChange={(checked) => {
                  setOverlayItems(prev => prev.map(item => 
                    item.id === overlayId 
                      ? { ...item, settings: { ...item.settings, enableBackground: checked } }
                      : item
                  ))
                }}
                colorTheme="cyan"
                size="sm"
              />
            </div>
            
            {/* Enabled Toggle */}
            <div className="flex items-center justify-between pt-2 border-t border-gray-600/30">
              <Label className="text-white text-sm font-medium">Enabled</Label>
              <Switch
                checked={overlay.enabled}
                onCheckedChange={() => toggleOverlayItem(overlay.id)}
                colorTheme="cyan"
              />
            </div>
          </div>
        )
        
      case "day_counter":
        return (
          <div className="space-y-3">
            <div className="flex items-center gap-2 mb-2">
              <Activity className="w-4 h-4 text-purple" />
              <Label className="text-white text-sm font-medium">Day Counter</Label>
            </div>
            
            {/* Text Size */}
            <div className="space-y-2">
              <Label className="text-white text-xs font-medium">Text Size</Label>
              <div className="flex items-center gap-2">
                <Slider
                  value={[overlay.settings?.textSize || 16]}
                  onValueChange={(value) => {
                    setOverlayItems(prev => prev.map(item =>
                      item.id === overlayId 
                        ? { ...item, settings: { ...item.settings, textSize: value[0] } }
                        : item
                    ))
                  }}
                  max={72}
                  min={8}
                  step={1}
                  className="flex-1"
                />
                <span className="text-white text-xs w-8 text-right">{overlay.settings?.textSize || 16}px</span>
              </div>
            </div>
            
            {/* Leading Zeros */}
            <div className="flex items-center justify-between">
              <Label className="text-white text-xs font-medium">Leading Zeros</Label>
              <Switch
                checked={overlay.settings?.leadingZeros || false}
                onCheckedChange={(checked) => {
                  setOverlayItems(prev => prev.map(item =>
                    item.id === overlayId 
                      ? { ...item, settings: { ...item.settings, leadingZeros: checked } }
                      : item
                  ))
                }}
                colorTheme="purple"
                size="sm"
              />
            </div>

            {/* Hide Prefix */}
            <div className="flex items-center justify-between">
              <Label className="text-white text-xs font-medium">Hide Prefix</Label>
              <Switch
                checked={overlay.settings?.hidePrefix || false}
                onCheckedChange={(checked) => {
                  setOverlayItems(prev => prev.map(item =>
                    item.id === overlayId 
                      ? { ...item, settings: { ...item.settings, hidePrefix: checked } }
                      : item
                  ))
                }}
                colorTheme="purple"
                size="sm"
              />
            </div>
            <div className="text-xs text-gray-400 -mt-1">
              Show "01" instead of "Day 01"
            </div>

            {/* Enable Background */}
            <div className="flex items-center justify-between">
              <Label className="text-white text-xs font-medium">Enable Background</Label>
              <Switch
                checked={overlay.settings?.enableBackground || false}
                onCheckedChange={(checked) => {
                  setOverlayItems(prev => prev.map(item => 
                    item.id === overlayId 
                      ? { ...item, settings: { ...item.settings, enableBackground: checked } }
                      : item
                  ))
                }}
                colorTheme="purple"
                size="sm"
              />
            </div>
            
            {/* Enabled Toggle */}
            <div className="flex items-center justify-between pt-2 border-t border-gray-600/30">
              <Label className="text-white text-sm font-medium">Enabled</Label>
              <Switch
                checked={overlay.enabled}
                onCheckedChange={() => toggleOverlayItem(overlay.id)}
                colorTheme="purple"
              />
            </div>
          </div>
        )
        
      case "date_time":
        return (
          <DateTimeFormatBuilder
            overlay={overlay}
            onSettingsChange={(newSettings) => {
              setOverlayItems(prev => prev.map(item =>
                item.id === overlay.id 
                  ? { ...item, settings: { ...item.settings, ...newSettings } }
                  : item
              ))
            }}
            onToggle={() => toggleOverlayItem(overlay.id)}
          />
        )
        
      default:
        return (
          <div className="space-y-3">
            <div className="flex items-center gap-2 mb-2">
              <overlay.icon className={cn("w-4 h-4", overlay.color)} />
              <Label className="text-white text-sm font-medium">{overlay.name}</Label>
            </div>
            
            {/* Basic settings for other overlay types */}
            <div className="flex items-center justify-between">
              <Label className="text-white text-sm font-medium">Enabled</Label>
              <Switch
                checked={overlay.enabled}
                onCheckedChange={() => toggleOverlayItem(overlay.id)}
                colorTheme="purple"
              />
            </div>
          </div>
        )
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 h-full">
      {/* Left Column - Preview */}
      <div className="lg:col-span-3 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Camera className="w-5 h-5 text-cyan" />
            <h3 className="text-lg font-semibold text-white">Live Preview</h3>
          </div>
          <div className="flex items-center gap-2">
            <Button
              onClick={handleGrabFreshFrame}
              disabled={isGrabbingFrame}
              size="sm"
              className="bg-red-500/80 hover:bg-red-500 text-white border-0"
            >
              {isGrabbingFrame ? (
                <>
                  <div className="w-4 h-4 mr-2 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Capturing...
                </>
              ) : (
                <>
                  <DownloadCloud className="w-4 h-4 mr-2" />
                  Grab Fresh Frame
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Image Preview with Overlays */}
        <div className="relative bg-black/20 border border-cyan/20 rounded-xl overflow-hidden aspect-video">
          {imageUrl ? (
            <div className="relative w-full h-full">
              <img 
                src={imageUrl} 
                alt="Camera preview"
                className="w-full h-full object-cover"
              />
              
              {/* Grid Overlay */}
              {showGrid && (
                <div className="absolute inset-0 pointer-events-none">
                  {/* 3x3 grid */}
                  <div className="absolute inset-0">
                    {/* Vertical lines */}
                    <div className="absolute left-1/3 top-0 bottom-0 w-px bg-cyan/50"></div>
                    <div className="absolute left-2/3 top-0 bottom-0 w-px bg-cyan/50"></div>
                    {/* Horizontal lines */}
                    <div className="absolute top-1/3 left-0 right-0 h-px bg-cyan/50"></div>
                    <div className="absolute top-2/3 left-0 right-0 h-px bg-cyan/50"></div>
                  </div>
                </div>
              )}
              
              {/* Margins Overlay */}
              {showMargins && (
                <div className="absolute inset-0 pointer-events-none">
                  <div 
                    className="absolute border border-purple/50 border-dashed"
                    style={{
                      top: `${globalSettings.yMargin}px`,
                      left: `${globalSettings.xMargin}px`,
                      right: `${globalSettings.xMargin}px`,
                      bottom: `${globalSettings.yMargin}px`,
                    }}
                  ></div>
                </div>
              )}
              
              {/* Overlay Elements */}
              {overlaysEnabled && (
                <>
                  {overlayItems.map((item) => {
                    if (!item.enabled) return null
                    
                    const style = {
                      opacity: globalSettings.opacity / 100,
                      filter: `drop-shadow(0 2px ${globalSettings.dropShadow / 10}px rgba(0,0,0,0.5))`,
                    }
                    
                    switch (item.type) {
                      case "weather":
                        return (
                          <div 
                            key={item.id}
                            className="absolute top-4 left-4 bg-black/60 backdrop-blur-sm rounded-lg p-3 border border-white/20"
                            style={style}
                          >
                            <div className="text-white text-sm font-medium flex items-center gap-2">
                              <Cloud className="w-4 h-4" />
                              72°
                              {item.settings?.display === "Temp + Symbol" && <Activity className="w-4 h-4" />}
                            </div>
                            {item.settings?.display === "Temp + Symbol" && (
                              <div className="text-white/80 text-xs">Sunny</div>
                            )}
                          </div>
                        )
                      case "watermark":
                        return (
                          <div 
                            key={item.id}
                            className="absolute bottom-4 right-4 bg-black/60 backdrop-blur-sm rounded-lg p-2 border border-white/20"
                            style={style}
                          >
                            <ImageIcon className="w-6 h-6 text-white" />
                          </div>
                        )
                      case "frame_number":
                        return (
                          <div 
                            key={item.id}
                            className="absolute bottom-4 left-4 bg-black/60 backdrop-blur-sm rounded-lg p-2 border border-white/20"
                            style={style}
                          >
                            <div className="text-white text-sm font-mono">#1,247</div>
                          </div>
                        )
                      case "date_time":
                        return (
                          <div 
                            key={item.id}
                            className="absolute top-4 right-4 bg-black/60 backdrop-blur-sm rounded-lg p-2 border border-white/20"
                            style={style}
                          >
                            <div className="text-white text-xs font-mono">
                              {formatDateTime(item.settings?.dateFormat || "YYYY-MM-DD HH:mm:ss")}
                            </div>
                          </div>
                        )
                      case "day_counter":
                        return (
                          <div 
                            key={item.id}
                            className="absolute top-4 left-1/2 transform -translate-x-1/2 bg-black/60 backdrop-blur-sm rounded-lg p-2 border border-white/20"
                            style={style}
                          >
                            <div className="text-white text-sm font-medium">Day 47</div>
                          </div>
                        )
                      case "custom_text":
                        return (
                          <div 
                            key={item.id}
                            className="absolute bottom-4 left-1/2 transform -translate-x-1/2 bg-black/60 backdrop-blur-sm rounded-lg p-2 border border-white/20"
                            style={style}
                          >
                            <div className="text-white text-sm">
                              {item.settings?.customText || "Custom Text"}
                            </div>
                          </div>
                        )
                      case "timelapse_name":
                        return (
                          <div 
                            key={item.id}
                            className="absolute bottom-4 right-1/2 transform translate-x-1/2 bg-black/60 backdrop-blur-sm rounded-lg p-2 border border-white/20"
                            style={style}
                          >
                            <div className="text-white text-sm font-medium">
                              {timelapse.name}
                            </div>
                          </div>
                        )
                      default:
                        return null
                    }
                  })}

                  {/* Selected overlay highlight */}
                  {selectedOverlay && (
                    <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 opacity-75 transition-opacity">
                      <div className="bg-purple/20 border border-purple/50 rounded-lg p-2 backdrop-blur-sm">
                        <div className="text-white text-sm">
                          {overlayItems.find(item => item.id === selectedOverlay)?.name}
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center w-full h-full text-gray-500">
              <div className="text-center">
                <Camera className="w-16 h-16 mx-auto text-gray-400 mb-4" />
                <p className="text-lg font-medium">Loading preview...</p>
              </div>
            </div>
          )}
        </div>

        {/* Bottom Controls */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            {/* Overlays Toggle */}
            <div className="flex items-center gap-3">
              <Label className="text-white text-sm font-medium">Overlays</Label>
              <div className="flex items-center">
                <span className={cn("text-xs mr-2", overlaysEnabled ? "text-gray-400" : "text-white")}>
                  OFF
                </span>
                <Switch
                  checked={overlaysEnabled}
                  onCheckedChange={setOverlaysEnabled}
                  colorTheme="pink"
                />
                <span className={cn("text-xs ml-2", overlaysEnabled ? "text-white" : "text-gray-400")}>
                  ON
                </span>
              </div>
            </div>

            {/* Show Grid Toggle */}
            <div className="flex items-center gap-3">
              <Label className="text-white text-sm font-medium">Show Grid</Label>
              <div className="flex items-center">
                <span className={cn("text-xs mr-2", showGrid ? "text-gray-400" : "text-white")}>
                  OFF
                </span>
                <Switch
                  checked={showGrid}
                  onCheckedChange={setShowGrid}
                  colorTheme="cyan"
                />
                <span className={cn("text-xs ml-2", showGrid ? "text-white" : "text-gray-400")}>
                  ON
                </span>
              </div>
            </div>

            {/* Show Margins Toggle */}
            <div className="flex items-center gap-3">
              <Label className="text-white text-sm font-medium">Show Margins</Label>
              <div className="flex items-center">
                <span className={cn("text-xs mr-2", showMargins ? "text-gray-400" : "text-white")}>
                  OFF
                </span>
                <Switch
                  checked={showMargins}
                  onCheckedChange={setShowMargins}
                  colorTheme="purple"
                />
                <span className={cn("text-xs ml-2", showMargins ? "text-white" : "text-gray-400")}>
                  ON
                </span>
              </div>
            </div>
          </div>

          {/* Export Button */}
          <Button
            onClick={handleExport}
            size="sm"
            variant="outline"
            className="border-cyan/30 text-white hover:bg-cyan/20"
          >
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Right Column - Controls */}
      <div className="space-y-4">
        {/* Globals Section */}
        <div className="space-y-3">
          <Button
            variant="ghost"
            onClick={() => setGlobalsExpanded(!globalsExpanded)}
            className="w-full justify-between p-3 h-auto bg-cyan/5 border border-cyan/20 rounded-lg hover:bg-cyan/10"
          >
            <div className="flex items-center gap-2">
              <Globe className="w-4 h-4 text-cyan" />
              <span className="text-white font-medium">Globals</span>
            </div>
            <ChevronRight 
              className={cn("w-4 h-4 text-cyan transition-transform", globalsExpanded && "rotate-90")} 
            />
          </Button>
          
          {globalsExpanded && (
            <div className="mt-3 space-y-4">
              {/* Global Settings Panel */}
              <div className="space-y-4 p-3 bg-black/10 border border-gray-600/20 rounded-lg">
                {/* Preset */}
                <div className="space-y-2">
                  <Label className="text-white text-xs font-medium">Preset</Label>
                  <Button
                    variant="outline"
                    className="w-full justify-between h-8 text-xs border-gray-500/50 text-white hover:bg-gray-700/50"
                    onClick={() => {
                      // TODO: Implement preset dropdown
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <Activity className="w-3 h-3 text-cyan" />
                      <span>{globalSettings.preset}</span>
                    </div>
                    <ChevronDown className="w-3 h-3" />
                  </Button>
                </div>
                
                {/* Margins */}
                <div className="space-y-2">
                  <Label className="text-white text-xs font-medium">Margins</Label>
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1">
                      <Label className="text-gray-400 text-xs">X:</Label>
                      <Input
                        type="number"
                        value={globalSettings.xMargin}
                        onChange={(e) => setGlobalSettings(prev => ({
                          ...prev,
                          xMargin: parseInt(e.target.value) || 0
                        }))}
                        className="w-12 h-6 text-xs bg-gray-800/50 border-gray-600/50 text-white"
                      />
                    </div>
                    <div className="flex items-center gap-1">
                      <Label className="text-gray-400 text-xs">Y:</Label>
                      <Input
                        type="number"
                        value={globalSettings.yMargin}
                        onChange={(e) => setGlobalSettings(prev => ({
                          ...prev,
                          yMargin: parseInt(e.target.value) || 0
                        }))}
                        className="w-12 h-6 text-xs bg-gray-800/50 border-gray-600/50 text-white"
                      />
                    </div>
                  </div>
                </div>
                
                {/* Opacity */}
                <div className="space-y-2">
                  <Label className="text-white text-xs font-medium">Opacity</Label>
                  <Slider
                    value={[globalSettings.opacity]}
                    onValueChange={(value) => setGlobalSettings(prev => ({
                      ...prev,
                      opacity: value[0]
                    }))}
                    max={100}
                    min={0}
                    step={1}
                    className="w-full"
                  />
                </div>
                
                {/* Drop Shadow */}
                <div className="space-y-2">
                  <Label className="text-white text-xs font-medium">Drop Shadow</Label>
                  <Slider
                    value={[globalSettings.dropShadow]}
                    onValueChange={(value) => setGlobalSettings(prev => ({
                      ...prev,
                      dropShadow: value[0]
                    }))}
                    max={100}
                    min={0}
                    step={1}
                    className="w-full"
                  />
                </div>
                
                {/* Font */}
                <div className="space-y-2">
                  <Label className="text-white text-xs font-medium">Font</Label>
                  <Button
                    variant="outline"
                    className="w-full justify-between h-8 text-xs border-gray-500/50 text-white hover:bg-gray-700/50"
                    onClick={() => {
                      // TODO: Implement font dropdown
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <Type className="w-3 h-3 text-gray-400" />
                      <span>{globalSettings.font}</span>
                    </div>
                    <ChevronDown className="w-3 h-3" />
                  </Button>
                </div>
                
                {/* Fill Color */}
                <div className="space-y-2">
                  <Label className="text-white text-xs font-medium">Fill Color</Label>
                  <div className="flex items-center gap-2">
                    <button
                      className="w-6 h-6 rounded-full border-2 border-white/20"
                      style={{ backgroundColor: globalSettings.fillColor }}
                      onClick={() => {
                        // TODO: Implement color picker
                      }}
                    />
                    <span className="text-white text-xs">{globalSettings.fillColor}</span>
                  </div>
                </div>

                {/* Background Color */}
                <div className="space-y-2">
                  <Label className="text-white text-xs font-medium">Background Color</Label>
                  <div className="flex items-center gap-2">
                    <button
                      className="w-6 h-6 rounded-full border-2 border-white/20"
                      style={{ backgroundColor: globalSettings.backgroundColor }}
                      onClick={() => {
                        // TODO: Implement color picker
                      }}
                    />
                    <span className="text-white text-xs">{globalSettings.backgroundColor}</span>
                  </div>
                </div>

                {/* Background Opacity */}
                <div className="space-y-2">
                  <Label className="text-white text-xs font-medium">Background Opacity</Label>
                  <div className="flex items-center gap-2">
                    <Slider
                      value={[globalSettings.backgroundOpacity]}
                      onValueChange={(value) => setGlobalSettings(prev => ({
                        ...prev,
                        backgroundOpacity: value[0]
                      }))}
                      max={100}
                      min={0}
                      step={1}
                      className="flex-1"
                    />
                    <span className="text-white text-xs w-8 text-right">{globalSettings.backgroundOpacity}%</span>
                  </div>
                </div>
              </div>
              
              {/* Overlay Items */}
              <div className="space-y-2">
                {overlayItems.map((item) => (
                  <div
                    key={item.id}
                    className={cn(
                      "flex items-center gap-3 p-3 rounded-lg border transition-all duration-200 cursor-pointer",
                      selectedOverlay === item.id
                        ? "bg-purple/10 border-purple/30"
                        : item.enabled 
                        ? "bg-cyan/10 border-cyan/30" 
                        : "bg-black/20 border-gray-600/30 hover:border-gray-500/50"
                    )}
                    onClick={() => {
                      if (selectedOverlay === item.id) {
                        setSelectedOverlay(null)
                      } else {
                        setSelectedOverlay(item.id)
                      }
                    }}
                  >
                    <div className="flex items-center gap-2 flex-1">
                      <div className={cn("w-2 h-2 rounded-full", item.enabled ? "bg-purple" : "bg-gray-500")} />
                      <item.icon className={cn("w-4 h-4", item.enabled ? item.color : "text-gray-500")} />
                      <span className={cn("text-sm font-medium", item.enabled ? "text-white" : "text-gray-400")}>
                        {item.name}
                      </span>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={item.enabled}
                        onCheckedChange={() => toggleOverlayItem(item.id)}
                        colorTheme="purple"
                        size="sm"
                      />
                      {selectedOverlay === item.id && (
                        <ChevronDown className="w-4 h-4 text-purple" />
                      )}
                    </div>
                  </div>
                ))}
                
                {/* Add New Overlay Button */}
                <Button
                  onClick={() => setShowAddModal(true)}
                  variant="outline"
                  className="w-full border-dashed border-gray-500/50 text-gray-400 hover:text-white hover:border-purple/50 hover:bg-purple/10"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Add Overlay
                </Button>
              </div>
              
              {/* Overlay-Specific Settings */}
              {selectedOverlay && (
                <div className="p-3 bg-purple/5 border border-purple/20 rounded-lg space-y-3">
                  {renderOverlaySettings(selectedOverlay)}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      
      {/* Add Overlay Modal */}
      <AddOverlayModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        onAdd={handleAddOverlay}
      />
    </div>
  )
}