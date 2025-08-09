// src/components/overlay-configuration-editor-unified.tsx
"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"
import {
  Settings,
  Type,
  Move,
  Eye,
  Plus,
  Trash2,
  Save,
  RotateCcw,
} from "lucide-react"
import type {
  OverlayConfig,
  OverlayItem,
  GlobalSettings,
} from "@/hooks/use-overlay-presets"
import { WatermarkConfig } from "@/components/overlay-config/watermark-config"
import { CustomTextConfig } from "@/components/overlay-config/custom-text-config"
import { FrameNumberConfig } from "@/components/overlay-config/frame-number-config"
import { DayNumberConfig } from "@/components/overlay-config/day-number-config"
import { TimelapseNameConfig } from "@/components/overlay-config/timelapse-name-config"

interface OverlayConfigurationEditorProps {
  config?: OverlayConfig
  onChange: (config: OverlayConfig) => void
  onSave?: () => void
  onReset?: () => void
  onPreview?: () => void
  saving?: boolean
  className?: string
}

const overlayTypes = [
  { value: "date_time", label: "Date & Time" },
  { value: "weather", label: "Weather" },
  { value: "temperature", label: "Temperature" },
  { value: "frame_number", label: "Frame Number" },
  { value: "day_number", label: "Day Counter" },
  { value: "custom_text", label: "Custom Text" },
  { value: "timelapse_name", label: "Timelapse Name" },
  { value: "watermark", label: "Watermark" },
]

const positions = [
  { x: "left", y: "top", label: "Top Left", value: "topLeft" },
  { x: "center", y: "top", label: "Top Center", value: "topCenter" },
  { x: "right", y: "top", label: "Top Right", value: "topRight" },
  { x: "left", y: "center", label: "Middle Left", value: "centerLeft" },
  { x: "center", y: "center", label: "Center", value: "center" },
  { x: "right", y: "center", label: "Middle Right", value: "centerRight" },
  { x: "left", y: "bottom", label: "Bottom Left", value: "bottomLeft" },
  { x: "center", y: "bottom", label: "Bottom Center", value: "bottomCenter" },
  { x: "right", y: "bottom", label: "Bottom Right", value: "bottomRight" },
]

const fonts = [
  { value: "dejavu", label: "DejaVu Sans" },
  { value: "arial", label: "Arial" },
  { value: "helvetica", label: "Helvetica" },
  { value: "times", label: "Times New Roman" },
]

export function OverlayConfigurationEditor({
  config,
  onChange,
  onSave,
  onReset,
  onPreview,
  saving = false,
  className,
}: OverlayConfigurationEditorProps) {
  const [currentConfig, setCurrentConfig] = useState<OverlayConfig>(
    config || {
      overlayItems: [],
      globalSettings: {
        opacity: 85,
        font: "dejavu",
        xMargin: 20,
        yMargin: 20,
        backgroundColor: "#000000",
        backgroundOpacity: 50,
        fillColor: "#FFFFFF",
        dropShadow: 2,
      },
    }
  )

  // Update local state when config prop changes
  useEffect(() => {
    if (config) {
      setCurrentConfig(config)
    }
  }, [config])

  const handleGlobalSettingChange = (key: keyof GlobalSettings, value: any) => {
    const newConfig = {
      ...currentConfig,
      globalSettings: {
        ...currentConfig.globalSettings,
        [key]: value,
      },
    }
    setCurrentConfig(newConfig)
    onChange(newConfig)
  }

  const handleOverlayItemAdd = (position: string, type: string) => {
    const newItem: OverlayItem = {
      id: `${type}_${Date.now()}`,
      type: type as any,
      position,
      enabled: true,
      settings: {
        textSize: 16,
        textColor: "#ffffff",
        enableBackground: false,
        backgroundColor: "#000000",
        backgroundOpacity: 50,
      },
    }

    const newConfig = {
      ...currentConfig,
      overlayItems: [...currentConfig.overlayItems, newItem],
    }
    setCurrentConfig(newConfig)
    onChange(newConfig)
  }

  const handleOverlayItemRemove = (id: string) => {
    const newConfig = {
      ...currentConfig,
      overlayItems: currentConfig.overlayItems.filter((item) => item.id !== id),
    }
    setCurrentConfig(newConfig)
    onChange(newConfig)
  }

  const handleOverlayItemUpdate = (
    id: string,
    updates: Partial<OverlayItem>
  ) => {
    const newConfig = {
      ...currentConfig,
      overlayItems: currentConfig.overlayItems.map((item) =>
        item.id === id ? { ...item, ...updates } : item
      ),
    }
    setCurrentConfig(newConfig)
    onChange(newConfig)
  }

  const handleOverlayItemSettingsUpdate = (
    id: string,
    settingsUpdates: any
  ) => {
    const item = currentConfig.overlayItems.find((item) => item.id === id)
    if (item) {
      const updatedItem = {
        ...item,
        settings: {
          ...item.settings,
          ...settingsUpdates,
        },
      }
      handleOverlayItemUpdate(id, updatedItem)
    }
  }

  const handleOverlayItemToggle = (id: string) => {
    const item = currentConfig.overlayItems.find((item) => item.id === id)
    if (item) {
      handleOverlayItemUpdate(id, { enabled: !item.enabled })
    }
  }

  return (
    <div className={className}>
      <Card className='mb-6'>
        <CardHeader>
          <CardTitle className='flex items-center space-x-2'>
            <Settings className='w-5 h-5' />
            <span>Global Settings</span>
          </CardTitle>
        </CardHeader>
        <CardContent className='space-y-6'>
          {/* Font Selection */}
          <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
            <div className='space-y-2'>
              <Label>Font</Label>
              <Select
                value={currentConfig.globalSettings.font}
                onValueChange={(value) =>
                  handleGlobalSettingChange("font", value)
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {fonts.map((font) => (
                    <SelectItem key={font.value} value={font.value}>
                      {font.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className='space-y-2'>
              <Label>Fill Color</Label>
              <Input
                type='color'
                value={currentConfig.globalSettings.fillColor}
                onChange={(e) =>
                  handleGlobalSettingChange("fillColor", e.target.value)
                }
                className='w-full h-10'
              />
            </div>
          </div>

          {/* Opacity Slider */}
          <div className='space-y-2'>
            <Label>Opacity: {currentConfig.globalSettings.opacity}%</Label>
            <Slider
              value={[currentConfig.globalSettings.opacity]}
              onValueChange={([value]) =>
                handleGlobalSettingChange("opacity", value)
              }
              max={100}
              step={1}
              className='w-full'
            />
          </div>

          {/* Drop Shadow Slider */}
          <div className='space-y-2'>
            <Label>
              Drop Shadow: {currentConfig.globalSettings.dropShadow}px
            </Label>
            <Slider
              value={[currentConfig.globalSettings.dropShadow]}
              onValueChange={([value]) =>
                handleGlobalSettingChange("dropShadow", value)
              }
              max={20}
              step={1}
              className='w-full'
            />
          </div>

          {/* Margins */}
          <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
            <div className='space-y-2'>
              <Label>X Margin</Label>
              <Input
                type='number'
                min='0'
                max='100'
                value={currentConfig.globalSettings.xMargin}
                onChange={(e) =>
                  handleGlobalSettingChange("xMargin", parseInt(e.target.value))
                }
              />
            </div>
            <div className='space-y-2'>
              <Label>Y Margin</Label>
              <Input
                type='number'
                min='0'
                max='100'
                value={currentConfig.globalSettings.yMargin}
                onChange={(e) =>
                  handleGlobalSettingChange("yMargin", parseInt(e.target.value))
                }
              />
            </div>
          </div>

          {/* Background Settings */}
          <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
            <div className='space-y-2'>
              <Label>Background Color</Label>
              <Input
                type='color'
                value={currentConfig.globalSettings.backgroundColor}
                onChange={(e) =>
                  handleGlobalSettingChange("backgroundColor", e.target.value)
                }
                className='w-full h-10'
              />
            </div>
            <div className='space-y-2'>
              <Label>
                Background Opacity:{" "}
                {currentConfig.globalSettings.backgroundOpacity}%
              </Label>
              <Slider
                value={[currentConfig.globalSettings.backgroundOpacity]}
                onValueChange={([value]) =>
                  handleGlobalSettingChange("backgroundOpacity", value)
                }
                max={100}
                step={1}
                className='w-full'
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className='flex items-center justify-between'>
            <div className='flex items-center space-x-2'>
              <Type className='w-5 h-5' />
              <span>Overlay Items</span>
              <Badge variant='secondary'>
                {currentConfig.overlayItems.length}
              </Badge>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {currentConfig.overlayItems.length === 0 ? (
            <div className='text-center py-8 text-muted-foreground'>
              <Type className='w-12 h-12 mx-auto mb-4 opacity-30' />
              <p className='text-lg font-medium mb-2'>
                No overlay items configured
              </p>
              <p>Add overlay items using the controls below</p>
            </div>
          ) : (
            <div className='space-y-4'>
              {currentConfig.overlayItems.map((item) => (
                <Card key={item.id} className='relative'>
                  <CardHeader className='pb-3'>
                    <div className='flex items-center justify-between'>
                      <div className='flex items-center space-x-2'>
                        <Badge variant='outline'>{item.position}</Badge>
                      </div>
                      <div className='flex items-center space-x-2'>
                        <Switch
                          checked={item.enabled}
                          onCheckedChange={() =>
                            handleOverlayItemToggle(item.id)
                          }
                        />
                        <Button
                          size='sm'
                          variant='destructive'
                          onClick={() => handleOverlayItemRemove(item.id)}
                        >
                          <Trash2 className='w-4 h-4' />
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className='pt-0'>
                    <div className='grid grid-cols-1 md:grid-cols-3 gap-4'>
                      {/* Position */}
                      <div className='space-y-2'>
                        <Label>Position</Label>
                        <Select
                          value={item.position}
                          onValueChange={(value) =>
                            handleOverlayItemUpdate(item.id, {
                              position: value,
                            })
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {positions.map((pos) => (
                              <SelectItem key={pos.value} value={pos.value}>
                                {pos.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Text Size */}
                      <div className='space-y-2'>
                        <Label>Text Size</Label>
                        <Input
                          type='number'
                          min='8'
                          max='72'
                          value={item.settings?.textSize || 16}
                          onChange={(e) =>
                            handleOverlayItemSettingsUpdate(item.id, {
                              textSize: parseInt(e.target.value),
                            })
                          }
                        />
                      </div>

                      {/* Text Color */}
                      <div className='space-y-2'>
                        <Label>Text Color</Label>
                        <Input
                          type='color'
                          value={item.settings?.textColor || "#ffffff"}
                          onChange={(e) =>
                            handleOverlayItemSettingsUpdate(item.id, {
                              textColor: e.target.value,
                            })
                          }
                          className='h-10'
                        />
                      </div>
                    </div>

                    {/* Type-specific settings */}
                    {item.type === "custom_text" && (
                      <div className='mt-4 space-y-2'>
                        <Label>Custom Text</Label>
                        <Input
                          value={item.settings?.customText || ""}
                          onChange={(e) =>
                            handleOverlayItemSettingsUpdate(item.id, {
                              customText: e.target.value,
                            })
                          }
                          placeholder='Enter custom text...'
                        />
                      </div>
                    )}

                    {item.type === "date_time" && (
                      <div className='mt-4 space-y-2'>
                        <Label>Date Format</Label>
                        <Input
                          value={
                            item.settings?.dateFormat || "MM/dd/yyyy HH:mm"
                          }
                          onChange={(e) =>
                            handleOverlayItemSettingsUpdate(item.id, {
                              dateFormat: e.target.value,
                            })
                          }
                          placeholder='MM/dd/yyyy HH:mm'
                        />
                      </div>
                    )}

                    {item.type === "watermark" && (
                      <div className='mt-4 col-span-3'>
                        <WatermarkConfig
                          settings={item.settings || {}}
                          onChange={(
                            newSettings: Partial<Record<string, any>>
                          ) =>
                            handleOverlayItemSettingsUpdate(
                              item.id,
                              newSettings
                            )
                          }
                        />
                      </div>
                    )}

                    {item.type === "custom_text" && (
                      <div className='mt-4 col-span-3'>
                        <CustomTextConfig
                          settings={item.settings || {}}
                          onChange={(
                            newSettings: Partial<Record<string, any>>
                          ) =>
                            handleOverlayItemSettingsUpdate(
                              item.id,
                              newSettings
                            )
                          }
                        />
                      </div>
                    )}

                    {item.type === "frame_number" && (
                      <div className='mt-4 col-span-3'>
                        <FrameNumberConfig
                          settings={item.settings || {}}
                          onChange={(
                            newSettings: Partial<Record<string, any>>
                          ) =>
                            handleOverlayItemSettingsUpdate(
                              item.id,
                              newSettings
                            )
                          }
                        />
                      </div>
                    )}

                    {item.type === "day_number" && (
                      <div className='mt-4 col-span-3'>
                        <DayNumberConfig
                          settings={item.settings || {}}
                          onChange={(
                            newSettings: Partial<Record<string, any>>
                          ) =>
                            handleOverlayItemSettingsUpdate(
                              item.id,
                              newSettings
                            )
                          }
                        />
                      </div>
                    )}

                    {item.type === "timelapse_name" && (
                      <div className='mt-4 col-span-3'>
                        <TimelapseNameConfig
                          settings={item.settings || {}}
                          timelapseTitle='Sample Timelapse'
                          onChange={(
                            newSettings: Partial<Record<string, any>>
                          ) =>
                            handleOverlayItemSettingsUpdate(
                              item.id,
                              newSettings
                            )
                          }
                        />
                      </div>
                    )}

                    {/* Background toggle */}
                    <div className='mt-4 flex items-center space-x-2'>
                      <Switch
                        checked={item.settings?.enableBackground || false}
                        onCheckedChange={(checked) =>
                          handleOverlayItemSettingsUpdate(item.id, {
                            enableBackground: checked,
                          })
                        }
                      />
                      <Label>Enable Background</Label>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          <Separator className='my-6' />

          {/* Add New Overlay Controls */}
          <div className='space-y-4'>
            <h3 className='text-lg font-medium'>Add Overlay Item</h3>
            <div className='grid grid-cols-1 md:grid-cols-3 gap-4'>
              {positions.slice(0, 9).map((position) => (
                <div key={position.value} className='space-y-2'>
                  <Label>{position.label}</Label>
                  <Select
                    onValueChange={(type) =>
                      handleOverlayItemAdd(position.value, type)
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder='Add overlay...' />
                    </SelectTrigger>
                    <SelectContent>
                      {overlayTypes.map((type) => (
                        <SelectItem key={type.value} value={type.value}>
                          {type.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              ))}
            </div>
          </div>

          {/* Action Buttons */}
          <div className='flex justify-between pt-6'>
            <div className='flex space-x-2'>
              {onReset && (
                <Button variant='outline' onClick={onReset}>
                  <RotateCcw className='w-4 h-4 mr-2' />
                  Reset
                </Button>
              )}
              {onPreview && (
                <Button variant='outline' onClick={onPreview}>
                  <Eye className='w-4 h-4 mr-2' />
                  Preview
                </Button>
              )}
            </div>
            {onSave && (
              <Button onClick={onSave} disabled={saving}>
                <Save className='w-4 h-4 mr-2' />
                {saving ? "Saving..." : "Save Configuration"}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
