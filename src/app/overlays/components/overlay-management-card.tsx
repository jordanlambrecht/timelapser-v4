// src/app/overlays/components/overlay-management-card.tsx
"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { Input } from "@/components/ui/input"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
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
  Square,
  Activity,
  Layers,
  Save,
  Loader2,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "@/lib/toast"
import {
  useOverlayPresets,
  type OverlayPreset,
  type OverlayConfig,
  type OverlayItem,
  type GlobalSettings,
} from "@/hooks/use-overlay-presets"
import { formatDateTime } from "@/utils/date-format-utils"

interface OverlayManagementCardProps {
  initialCameraId?: number
}

export function OverlayManagementCard({
  initialCameraId = 1,
}: OverlayManagementCardProps) {
  const [imageUrl, setImageUrl] = useState<string>("")
  const [isGrabbingFrame, setIsGrabbingFrame] = useState(false)
  const [overlaysEnabled, setOverlaysEnabled] = useState(true)
  const [liveViewEnabled, setLiveViewEnabled] = useState(true)
  const [showGrid, setShowGrid] = useState(false)
  const [showMargins, setShowMargins] = useState(false)
  const [globalsExpanded, setGlobalsExpanded] = useState(true)
  const [selectedOverlay, setSelectedOverlay] = useState<string | null>(null)
  const [currentPresetId, setCurrentPresetId] = useState<number | null>(null)
  const [presetName, setPresetName] = useState("")
  const [presetDescription, setPresetDescription] = useState("")
  const [isSaving, setIsSaving] = useState(false)

  const { presets, loading, createPreset, updatePreset } = useOverlayPresets()

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
    preset: "Custom Configuration",
  })

  // Sample overlay items - matches overlays-tab pattern
  const [overlayItems, setOverlayItems] = useState<OverlayItem[]>([
    {
      id: "weather",
      type: "weather",
      position: "topLeft",
      enabled: true,
      settings: {
        unit: "Celsius",
        display: "both",
        textSize: 16,
        enableBackground: true,
      },
    },
    {
      id: "date_time",
      type: "date_time",
      position: "topRight",
      enabled: false,
      settings: {
        dateFormat: "MM/dd/yyyy HH:mm",
        textSize: 16,
        enableBackground: false,
      },
    },
    {
      id: "frame_number",
      type: "frame_number",
      position: "bottomLeft",
      enabled: false,
      settings: {
        textSize: 16,
        leadingZeros: false,
        enableBackground: false,
      },
    },
  ])

  // Initialize image URL
  useEffect(() => {
    setImageUrl(
      `/api/cameras/${initialCameraId}/latest-image/small?t=${Date.now()}`
    )
  }, [initialCameraId])

  const handleGrabFreshFrame = async () => {
    setIsGrabbingFrame(true)
    try {
      const response = await fetch(
        `/api/overlays/fresh-photo/${initialCameraId}`,
        {
          method: "POST",
        }
      )

      if (!response.ok) {
        // If fresh capture fails, fall back to refreshing the latest image
        console.warn(
          "Fresh capture failed, falling back to latest image refresh"
        )
        setImageUrl(
          `/api/cameras/${initialCameraId}/latest-image/small?t=${Date.now()}`
        )
        toast.success("Image refreshed!")
        return
      }

      setTimeout(() => {
        setImageUrl(
          `/api/cameras/${initialCameraId}/latest-image/small?t=${Date.now()}`
        )
        toast.success("Fresh frame captured!")
      }, 2000)
    } catch (error) {
      console.error("Failed to grab fresh frame:", error)
      // Fall back to refreshing the latest image
      setImageUrl(
        `/api/cameras/${initialCameraId}/latest-image/small?t=${Date.now()}`
      )
      toast.error("Fresh capture failed, refreshed latest image instead")
    } finally {
      setIsGrabbingFrame(false)
    }
  }

  const toggleOverlayItem = (id: string) => {
    setOverlayItems((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, enabled: !item.enabled } : item
      )
    )
  }

  const handleAddOverlay = (overlayType: string) => {
    const overlayTypeMap: Record<string, { icon: any; color: string }> = {
      weather: { icon: Cloud, color: "text-purple" },
      watermark: { icon: ImageIcon, color: "text-cyan" },
      frame_number: { icon: Hash, color: "text-pink" },
      date_time: { icon: Calendar, color: "text-cyan" },
      day_number: { icon: Activity, color: "text-purple" },
      custom_text: { icon: Type, color: "text-pink" },
      timelapse_name: { icon: FileText, color: "text-cyan" },
    }

    const config = overlayTypeMap[overlayType]
    if (!config) return

    const getDefaultSettings = (type: string) => {
      switch (type) {
        case "weather":
          return {
            unit: "Celsius",
            display: "both",
            textSize: 16,
            enableBackground: false,
          }
        case "watermark":
          return { imageScale: 100, imageUrl: "" }
        case "frame_number":
          return { textSize: 16, leadingZeros: false, enableBackground: false }
        case "date_time":
          return {
            dateFormat: "YYYY-MM-DD HH:mm:ss",
            textSize: 16,
            enableBackground: false,
          }
        case "day_number":
          return {
            leadingZeros: false,
            textSize: 16,
            hidePrefix: false,
            enableBackground: false,
          }
        case "custom_text":
          return {
            customText: "Custom Text",
            textSize: 16,
            enableBackground: false,
          }
        case "timelapse_name":
          return { textSize: 16, enableBackground: false }
        default:
          return {}
      }
    }

    const newOverlay: OverlayItem = {
      id: `${overlayType}_${Date.now()}`,
      type: overlayType as any,
      position: "topLeft",
      enabled: true,
      settings: getDefaultSettings(overlayType),
    }

    setOverlayItems((prev) => [...prev, newOverlay])
    setSelectedOverlay(newOverlay.id)
    toast.success(`${overlayType} overlay added!`)
  }

  const handleSaveAsPreset = async () => {
    if (!presetName.trim()) {
      toast.error("Please enter a preset name")
      return
    }

    setIsSaving(true)
    try {
      const overlayConfig: OverlayConfig = {
        globalSettings,
        overlayItems,
      }

      if (currentPresetId) {
        // Update existing preset
        await updatePreset(currentPresetId, {
          name: presetName,
          description: presetDescription,
          overlay_config: overlayConfig,
        })
        toast.success("Preset updated successfully!")
      } else {
        // Create new preset
        const newPreset = await createPreset({
          name: presetName,
          description: presetDescription,
          overlay_config: overlayConfig,
        })
        if (newPreset) {
          setCurrentPresetId(newPreset.id)
          toast.success("Preset created successfully!")
        }
      }
    } catch (error) {
      toast.error("Failed to save preset")
    } finally {
      setIsSaving(false)
    }
  }

  const loadPreset = (preset: OverlayPreset) => {
    // Preset already uses unified format
    const config = preset.overlay_config

    setGlobalSettings(config.globalSettings)
    setOverlayItems(config.overlayItems)
    setCurrentPresetId(preset.id)
    setPresetName(preset.name)
    setPresetDescription(preset.description)
    toast.success(`Loaded preset: ${preset.name}`)
  }

  const handleExport = async () => {
    try {
      const overlayConfig: OverlayConfig = { globalSettings, overlayItems }
      const dataStr = JSON.stringify(overlayConfig, null, 2)
      const dataBlob = new Blob([dataStr], { type: "application/json" })
      const url = URL.createObjectURL(dataBlob)
      const link = document.createElement("a")
      link.href = url
      link.download = `overlay-config-${Date.now()}.json`
      link.click()
      toast.success("Overlay configuration exported!")
    } catch (error) {
      toast.error("Failed to export configuration")
    }
  }

  const renderOverlaySettings = (overlayId: string) => {
    const overlay = overlayItems.find((item) => item.id === overlayId)
    if (!overlay) return null

    const getOverlayIcon = (type: string) => {
      switch (type) {
        case "weather":
          return Cloud
        case "watermark":
          return ImageIcon
        case "frame_number":
          return Hash
        case "date_time":
          return Calendar
        case "day_number":
          return Activity
        case "custom_text":
          return Type
        case "timelapse_name":
          return FileText
        default:
          return SettingsIcon
      }
    }

    const Icon = getOverlayIcon(overlay.type)

    return (
      <div className='space-y-3'>
        <div className='flex items-center gap-2 mb-2'>
          <Icon className='w-4 h-4 text-purple' />
          <Label className='text-white text-sm font-medium'>
            {overlay.type.replace("_", " ")}
          </Label>
        </div>

        {/* Common settings */}
        <div className='space-y-2'>
          <Label className='text-white text-xs font-medium'>Text Size</Label>
          <div className='flex items-center gap-2'>
            <Slider
              value={[overlay.settings?.textSize || 16]}
              onValueChange={(value) => {
                setOverlayItems((prev) =>
                  prev.map((item) =>
                    item.id === overlayId
                      ? {
                          ...item,
                          settings: { ...item.settings, textSize: value[0] },
                        }
                      : item
                  )
                )
              }}
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
            onCheckedChange={(checked) => {
              setOverlayItems((prev) =>
                prev.map((item) =>
                  item.id === overlayId
                    ? {
                        ...item,
                        settings: {
                          ...item.settings,
                          enableBackground: checked,
                        },
                      }
                    : item
                )
              )
            }}
            colorTheme='cyan'
          />
        </div>

        {/* Enabled Toggle */}
        <div className='flex items-center justify-between pt-2 border-t border-gray-600/30'>
          <Label className='text-white text-sm font-medium'>Enabled</Label>
          <Switch
            checked={overlay.enabled}
            onCheckedChange={() => toggleOverlayItem(overlay.id)}
            colorTheme='cyan'
          />
        </div>
      </div>
    )
  }

  return (
    <Card className='transition-all duration-300 glass hover:glow'>
      <CardHeader>
        <CardTitle className='flex items-center space-x-2'>
          <Layers className='w-5 h-5 text-purple' />
          <span>Overlay Management</span>
        </CardTitle>
        <CardDescription>
          Create and configure overlay presets with live preview. Configure
          text, weather data, and image overlays with custom positioning.
        </CardDescription>
      </CardHeader>

      <CardContent>
        <div className='grid grid-cols-1 lg:grid-cols-4 gap-6'>
          {/* Left Column - Preview */}
          <div className='lg:col-span-3 space-y-4'>
            <div className='flex items-center justify-between'>
              <div className='flex items-center gap-2'>
                <Camera className='w-5 h-5 text-cyan' />
                <h3 className='text-lg font-semibold text-white'>
                  Live Preview
                </h3>
              </div>
              <div className='flex items-center gap-2'>
                <Button
                  onClick={handleGrabFreshFrame}
                  disabled={isGrabbingFrame}
                  className='bg-red-500/80 hover:bg-red-500 text-white border-0'
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

            {/* Image Preview with Overlays */}
            <div className='relative bg-black/20 border border-cyan/20 rounded-xl overflow-hidden aspect-video'>
              {imageUrl ? (
                <div className='relative w-full h-full'>
                  <img
                    src={imageUrl}
                    alt='Camera preview'
                    className='w-full h-full object-cover'
                  />

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

                  {/* Overlay Elements Preview */}
                  {overlaysEnabled && (
                    <>
                      {overlayItems.map((item) => {
                        if (!item.enabled) return null

                        const style = {
                          opacity: globalSettings.opacity / 100,
                          filter: `drop-shadow(0 2px ${
                            globalSettings.dropShadow / 10
                          }px rgba(0,0,0,0.5))`,
                        }

                        const getPositionStyles = (position: string) => {
                          switch (position) {
                            case "topLeft":
                              return "top-4 left-4"
                            case "topCenter":
                              return "top-4 left-1/2 transform -translate-x-1/2"
                            case "topRight":
                              return "top-4 right-4"
                            case "centerLeft":
                              return "top-1/2 left-4 transform -translate-y-1/2"
                            case "center":
                              return "top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2"
                            case "centerRight":
                              return "top-1/2 right-4 transform -translate-y-1/2"
                            case "bottomLeft":
                              return "bottom-4 left-4"
                            case "bottomCenter":
                              return "bottom-4 left-1/2 transform -translate-x-1/2"
                            case "bottomRight":
                              return "bottom-4 right-4"
                            default:
                              return "top-4 left-4"
                          }
                        }

                        return (
                          <div
                            key={item.id}
                            className={cn(
                              "absolute bg-black/60 backdrop-blur-sm rounded-lg p-2 border border-white/20",
                              getPositionStyles(item.position)
                            )}
                            style={style}
                          >
                            <div className='text-white text-sm font-medium flex items-center gap-2'>
                              {item.type === "weather" && (
                                <Cloud className='w-4 h-4' />
                              )}
                              {item.type === "date_time" &&
                                formatDateTime(
                                  item.settings?.dateFormat ||
                                    "MM/dd/yyyy HH:mm"
                                )}
                              {item.type === "frame_number" && "#1,247"}
                              {item.type === "weather" && "72° Sunny"}
                              {item.type === "custom_text" &&
                                (item.settings?.customText || "Custom Text")}
                              {item.type === "timelapse_name" &&
                                "Sample Timelapse"}
                            </div>
                          </div>
                        )
                      })}
                    </>
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

            {/* Bottom Controls */}
            <div className='flex items-center justify-between'>
              <div className='flex items-center gap-6'>
                {/* Overlays Toggle */}
                <div className='flex items-center gap-3'>
                  <Label className='text-white text-sm font-medium'>
                    Overlays
                  </Label>
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
                      onCheckedChange={setOverlaysEnabled}
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
                  <Label className='text-white text-sm font-medium'>
                    Show Grid
                  </Label>
                  <Switch
                    checked={showGrid}
                    onCheckedChange={setShowGrid}
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
                    onCheckedChange={setShowMargins}
                    colorTheme='cyan'
                  />
                </div>
              </div>

              {/* Export Button */}
              <Button
                onClick={handleExport}
                variant='outline'
                className='border-cyan/30 text-white hover:bg-cyan/20'
              >
                <Download className='w-4 h-4 mr-2' />
                Export Config
              </Button>
            </div>
          </div>

          {/* Right Column - Controls */}
          <div className='space-y-4'>
            {/* Preset Management */}
            <div className='space-y-3'>
              <div className='flex items-center gap-2'>
                <Save className='w-4 h-4 text-cyan' />
                <h4 className='text-sm font-medium text-white'>
                  Preset Management
                </h4>
              </div>

              <div className='space-y-2'>
                <Input
                  placeholder='Preset name'
                  value={presetName}
                  onChange={(e) => setPresetName(e.target.value)}
                  className='bg-gray-800/50 border-gray-600/50 text-white placeholder-gray-400'
                />
                <Input
                  placeholder='Description (optional)'
                  value={presetDescription}
                  onChange={(e) => setPresetDescription(e.target.value)}
                  className='bg-gray-800/50 border-gray-600/50 text-white placeholder-gray-400'
                />
                <Button
                  onClick={handleSaveAsPreset}
                  disabled={isSaving || !presetName.trim()}
                  className='w-full bg-purple/20 hover:bg-purple/30 text-white border border-purple/30'
                >
                  {isSaving ? (
                    <Loader2 className='w-4 h-4 mr-2 animate-spin' />
                  ) : (
                    <Save className='w-4 h-4 mr-2' />
                  )}
                  {currentPresetId ? "Update Preset" : "Save as Preset"}
                </Button>
              </div>

              {/* Load Preset */}
              {presets.length > 0 && (
                <div className='space-y-2'>
                  <Label className='text-white text-xs font-medium'>
                    Load Preset
                  </Label>
                  <div className='space-y-1 max-h-32 overflow-y-auto'>
                    {presets.map((preset) => (
                      <Button
                        key={preset.id}
                        onClick={() => loadPreset(preset)}
                        variant='ghost'
                        className='w-full justify-start text-left h-auto p-2 hover:bg-cyan/10'
                      >
                        <div>
                          <div className='text-white text-xs font-medium'>
                            {preset.name}
                          </div>
                          {preset.description && (
                            <div className='text-gray-400 text-xs'>
                              {preset.description}
                            </div>
                          )}
                        </div>
                      </Button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Globals Section */}
            <div className='space-y-3'>
              <Button
                variant='ghost'
                onClick={() => setGlobalsExpanded(!globalsExpanded)}
                className='w-full justify-between p-3 h-auto bg-cyan/5 border border-cyan/20 rounded-lg hover:bg-cyan/10'
              >
                <div className='flex items-center gap-2'>
                  <Globe className='w-4 h-4 text-cyan' />
                  <span className='text-white font-medium'>
                    Global Settings
                  </span>
                </div>
                <ChevronRight
                  className={cn(
                    "w-4 h-4 text-cyan transition-transform",
                    globalsExpanded && "rotate-90"
                  )}
                />
              </Button>

              {globalsExpanded && (
                <div className='mt-3 space-y-4'>
                  {/* Global Settings Panel */}
                  <div className='space-y-4 p-3 bg-black/10 border border-gray-600/20 rounded-lg'>
                    {/* Margins */}
                    <div className='space-y-2'>
                      <Label className='text-white text-xs font-medium'>
                        Margins
                      </Label>
                      <div className='flex items-center gap-2'>
                        <div className='flex items-center gap-1'>
                          <Label className='text-gray-400 text-xs'>X:</Label>
                          <Input
                            type='number'
                            value={globalSettings.xMargin}
                            onChange={(e) =>
                              setGlobalSettings((prev) => ({
                                ...prev,
                                xMargin: parseInt(e.target.value) || 0,
                              }))
                            }
                            className='w-12 h-6 text-xs bg-gray-800/50 border-gray-600/50 text-white'
                          />
                        </div>
                        <div className='flex items-center gap-1'>
                          <Label className='text-gray-400 text-xs'>Y:</Label>
                          <Input
                            type='number'
                            value={globalSettings.yMargin}
                            onChange={(e) =>
                              setGlobalSettings((prev) => ({
                                ...prev,
                                yMargin: parseInt(e.target.value) || 0,
                              }))
                            }
                            className='w-12 h-6 text-xs bg-gray-800/50 border-gray-600/50 text-white'
                          />
                        </div>
                      </div>
                    </div>

                    {/* Opacity */}
                    <div className='space-y-2'>
                      <Label className='text-white text-xs font-medium'>
                        Opacity
                      </Label>
                      <Slider
                        value={[globalSettings.opacity]}
                        onValueChange={(value) =>
                          setGlobalSettings((prev) => ({
                            ...prev,
                            opacity: value[0],
                          }))
                        }
                        max={100}
                        min={0}
                        step={1}
                        className='w-full'
                      />
                    </div>

                    {/* Drop Shadow */}
                    <div className='space-y-2'>
                      <Label className='text-white text-xs font-medium'>
                        Drop Shadow
                      </Label>
                      <Slider
                        value={[globalSettings.dropShadow]}
                        onValueChange={(value) =>
                          setGlobalSettings((prev) => ({
                            ...prev,
                            dropShadow: value[0],
                          }))
                        }
                        max={100}
                        min={0}
                        step={1}
                        className='w-full'
                      />
                    </div>
                  </div>

                  {/* Overlay Items */}
                  <div className='space-y-2'>
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
                        <div className='flex items-center gap-2 flex-1'>
                          <div
                            className={cn(
                              "w-2 h-2 rounded-full",
                              item.enabled ? "bg-purple" : "bg-gray-500"
                            )}
                          />
                          <span
                            className={cn(
                              "text-sm font-medium",
                              item.enabled ? "text-white" : "text-gray-400"
                            )}
                          >
                            {item.type.replace("_", " ")}
                          </span>
                        </div>

                        <div className='flex items-center gap-2'>
                          <Switch
                            checked={item.enabled}
                            onCheckedChange={() => toggleOverlayItem(item.id)}
                            colorTheme='cyan'
                          />
                          {selectedOverlay === item.id && (
                            <ChevronDown className='w-4 h-4 text-purple' />
                          )}
                        </div>
                      </div>
                    ))}

                    {/* Add New Overlay Button */}
                    <Button
                      onClick={() => handleAddOverlay("custom_text")}
                      variant='outline'
                      className='w-full border-dashed border-gray-500/50 text-gray-400 hover:text-white hover:border-purple/50 hover:bg-purple/10'
                    >
                      <Plus className='w-4 h-4 mr-2' />
                      Add Overlay
                    </Button>
                  </div>

                  {/* Overlay-Specific Settings */}
                  {selectedOverlay && (
                    <div className='p-3 bg-purple/5 border border-purple/20 rounded-lg space-y-3'>
                      {renderOverlaySettings(selectedOverlay)}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
