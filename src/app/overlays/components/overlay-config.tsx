// src/app/overlays/components/overlay-config.tsx
"use client"

import { useRef, useEffect, useState } from "react"
import { ColorPicker, useColor } from "react-color-palette"
import "react-color-palette/css"

import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { NumberInput } from "@/components/ui/number-input"
import { ThemedSlider } from "@/components/ui/themed-slider"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Upload, X, Image } from "lucide-react"
import {
  POSITION_LABELS,
  OVERLAY_TYPES,
  type GridPosition,
  type OverlayType,
} from "@/lib/overlay-presets-data"
import type { OverlayItem } from "@/hooks/use-overlay-presets"
import { useOverlayAssets } from "@/hooks/use-overlay-assets"

interface OverlayConfigProps {
  overlayItems: OverlayItem[]
  onUpdateOverlay: (id: string, updates: Partial<OverlayItem>) => void
  selectedItemId?: string | null
}

export function OverlayConfig({
  overlayItems,
  onUpdateOverlay,
  selectedItemId,
}: OverlayConfigProps) {
  const configRef = useRef<HTMLDivElement>(null)
  const {
    uploadAsset,
    getAssetUrl,
    isLoading: assetLoading,
  } = useOverlayAssets()

  const getOverlayTypeData = (type: OverlayType) => {
    return OVERLAY_TYPES.find((t) => t.value === type)
  }

  // Color picker component
  const ColorPickerComponent = ({
    color,
    onChange,
  }: {
    color: string
    onChange: (color: string) => void
  }) => {
    const [colorState, setColorState] = useColor(color)

    useEffect(() => {
      setColorState({ ...colorState, hex: color })
    }, [color])

    return (
      <ColorPicker
        color={colorState}
        onChange={(newColor) => {
          setColorState(newColor)
          onChange(newColor.hex)
        }}
      />
    )
  }

  // Enhanced image upload handler with hybrid approach
  const handleImageUpload = async (itemId: string, file: File) => {
    // Immediate preview using FileReader for UX
    const reader = new FileReader()
    reader.onload = (e) => {
      const previewUrl = e.target?.result as string
      onUpdateOverlay(itemId, {
        settings: {
          ...overlayItems.find((item) => item.id === itemId)?.settings,
          imageUrl: previewUrl,
          isUploading: true, // Add loading state
        },
      })
    }
    reader.readAsDataURL(file)

    // Upload to backend for persistent storage
    try {
      const asset = await uploadAsset(file)
      if (asset) {
        // Replace preview with persistent asset URL
        onUpdateOverlay(itemId, {
          settings: {
            ...overlayItems.find((item) => item.id === itemId)?.settings,
            imageUrl: getAssetUrl(asset.id),
            assetId: asset.id,
            isUploading: false,
          },
        })
      }
    } catch (error) {
      console.error("Failed to upload asset to backend:", error)
      // Keep the preview URL as fallback
      onUpdateOverlay(itemId, {
        settings: {
          ...overlayItems.find((item) => item.id === itemId)?.settings,
          isUploading: false,
        },
      })
    }
  }

  if (overlayItems.length === 0) {
    return (
      <div className='text-center py-8'>
        <p className='text-grey-light/60'>No overlays configured yet.</p>
        <p className='text-grey-light/40 text-sm mt-1'>
          Click on grid positions above to add overlays.
        </p>
      </div>
    )
  }

  return (
    <div ref={configRef} className='space-y-3'>
      {overlayItems.map((item) => {
        const typeData = getOverlayTypeData(item.type as OverlayType)
        const settings = item.settings || {}

        return (
          <div key={item.id} className='space-y-3'>
            <div className='flex items-center space-x-2'>
              <Badge
                variant='outline'
                className='text-xs text-grey-light/60 border-purple-muted/30'
              >
                {item.position}
              </Badge>
            </div>

            <div className='grid grid-cols-2 gap-3'>
              {/* Text Size */}
              <div className='space-y-1'>
                <Label className='text-white text-xs'>Size</Label>
                <NumberInput
                  value={settings.textSize || 16}
                  onChange={(value) =>
                    onUpdateOverlay(item.id, {
                      settings: { ...settings, textSize: value },
                    })
                  }
                  min={8}
                  max={72}
                  className='bg-blue/20 border-purple-muted/50 focus:border-pink/50 h-8 text-xs'
                />
              </div>

              {/* Text Color */}
              <div className='space-y-1'>
                <Label className='text-white text-xs'>Color</Label>
                <Popover>
                  <PopoverTrigger asChild>
                    <div className='flex items-center space-x-1 cursor-pointer'>
                      <div
                        className='w-8 h-8 rounded border-2 border-purple-muted/50'
                        style={{
                          backgroundColor: settings.textColor || "#ffffff",
                        }}
                      />
                      <Input
                        value={settings.textColor || "#ffffff"}
                        onChange={(e) =>
                          onUpdateOverlay(item.id, {
                            settings: {
                              ...settings,
                              textColor: e.target.value,
                            },
                          })
                        }
                        className='flex-1 text-xs bg-blue/20 border-purple-muted/50 focus:border-pink/50 text-white h-8'
                        placeholder='#FFFFFF'
                      />
                    </div>
                  </PopoverTrigger>
                  <PopoverContent className='w-auto p-0 bg-black border-purple-muted/50'>
                    <ColorPickerComponent
                      color={settings.textColor || "#ffffff"}
                      onChange={(color) =>
                        onUpdateOverlay(item.id, {
                          settings: { ...settings, textColor: color },
                        })
                      }
                    />
                  </PopoverContent>
                </Popover>
              </div>

              {/* Custom Text Field */}
              {item.type === "custom_text" && (
                <div className='space-y-1 col-span-2'>
                  <Label className='text-white text-xs'>Custom Text</Label>
                  <Input
                    value={settings.customText || ""}
                    onChange={(e) =>
                      onUpdateOverlay(item.id, {
                        settings: { ...settings, customText: e.target.value },
                      })
                    }
                    placeholder='Enter your custom text...'
                    className='bg-blue/20 border-purple-muted/50 focus:border-pink/50 text-white h-8 text-xs'
                  />
                </div>
              )}

              {/* Date Format for date/time overlays */}
              {(item.type.includes("date") || item.type.includes("time")) && (
                <div className='space-y-1 col-span-2'>
                  <Label className='text-white text-xs'>Date Format</Label>
                  <Input
                    value={settings.dateFormat || "MM/dd/yyyy HH:mm"}
                    onChange={(e) =>
                      onUpdateOverlay(item.id, {
                        settings: { ...settings, dateFormat: e.target.value },
                      })
                    }
                    placeholder='MM/dd/yyyy HH:mm'
                    className='bg-blue/20 border-purple-muted/50 focus:border-pink/50 text-white h-8 text-xs'
                  />
                  <p className='text-xs text-grey-light/60'>
                    Use: MM/dd/yyyy, HH:mm, yyyy-MM-dd HH:mm:ss
                  </p>
                </div>
              )}

              {/* Weather Display Mode for weather overlays */}
              {(item.type === "weather_conditions" ||
                item.type === "weather") && (
                <div className='space-y-1 col-span-2'>
                  <Label className='text-white text-xs'>Weather Display</Label>
                  <select
                    value={settings.conditions_display || "icon"}
                    onChange={(e) =>
                      onUpdateOverlay(item.id, {
                        settings: {
                          ...settings,
                          conditions_display: e.target.value,
                        },
                      })
                    }
                    className='w-full h-8 text-xs bg-blue/20 border-purple-muted/50 focus:border-pink/50 text-white rounded px-2'
                  >
                    <option value='icon'>Weather Icons (☀️ 🌧️ ⛅)</option>
                    <option value='text'>Text Description</option>
                  </select>
                  <p className='text-xs text-grey-light/60'>
                    Choose between weather icons or text descriptions
                  </p>
                </div>
              )}

              {/* Image Upload for watermark/image overlays */}
              {item.type === "watermark" && (
                <div className='space-y-1 col-span-2'>
                  <Label className='text-white text-xs'>Image Upload</Label>

                  {/* Current Image Preview */}
                  {settings.imageUrl && (
                    <div className='relative'>
                      <div className='flex items-center space-x-2 p-2 bg-purple-muted/10 rounded border border-purple-muted/30'>
                        <Image className='w-4 h-4 text-cyan' />
                        <span className='text-xs text-white truncate flex-1'>
                          Image uploaded
                        </span>
                        <Button
                          size='sm'
                          variant='ghost'
                          onClick={() =>
                            onUpdateOverlay(item.id, {
                              settings: { ...settings, imageUrl: undefined },
                            })
                          }
                          className='h-6 w-6 p-0 hover:bg-failure/20 hover:text-failure'
                        >
                          <X className='w-3 h-3' />
                        </Button>
                      </div>
                      <div className='mt-2'>
                        <img
                          src={settings.imageUrl}
                          alt='Watermark preview'
                          className='max-w-full h-16 object-contain rounded border border-purple-muted/30'
                        />
                      </div>
                    </div>
                  )}

                  {/* Upload Button */}
                  <div className='relative'>
                    <input
                      type='file'
                      accept='image/*'
                      onChange={(e) => {
                        const file = e.target.files?.[0]
                        if (file) handleImageUpload(item.id, file)
                      }}
                      className='absolute inset-0 opacity-0 cursor-pointer'
                      id={`image-upload-${item.id}`}
                    />
                    <Button
                      variant='outline'
                      className='w-full h-8 text-xs border-purple-muted/50 text-cyan hover:bg-cyan/10 hover:border-cyan/50'
                      asChild
                      disabled={assetLoading || settings.isUploading}
                    >
                      <label
                        htmlFor={`image-upload-${item.id}`}
                        className='cursor-pointer flex items-center space-x-2'
                      >
                        <Upload className='w-3 h-3' />
                        <span>
                          {settings.isUploading
                            ? "Uploading..."
                            : settings.imageUrl
                            ? "Change Image"
                            : "Upload Image"}
                        </span>
                      </label>
                    </Button>
                  </div>

                  {/* Image Scale */}
                  {settings.imageUrl && (
                    <div className='space-y-1'>
                      <ThemedSlider
                        label='Image Scale'
                        value={settings.imageScale || 100}
                        onChange={(value) =>
                          onUpdateOverlay(item.id, {
                            settings: { ...settings, imageScale: value },
                          })
                        }
                        min={10}
                        max={200}
                        step={5}
                        unit='%'
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
