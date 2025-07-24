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
import { POSITION_LABELS, OVERLAY_TYPES, type GridPosition, type OverlayType } from "@/lib/overlay-presets-data"

interface OverlayItem {
  type: OverlayType
  customText?: string
  textSize: number
  textColor: string
  backgroundColor?: string
  backgroundOpacity: number
  dateFormat?: string
  imageUrl?: string
  imageScale: number
}

interface OverlayConfigProps {
  overlayPositions: Partial<Record<GridPosition, OverlayItem>>
  onUpdateOverlay: (position: GridPosition, updates: Partial<OverlayItem>) => void
  selectedPosition?: GridPosition | null
}

export function OverlayConfig({ overlayPositions, onUpdateOverlay, selectedPosition }: OverlayConfigProps) {
  const configRef = useRef<HTMLDivElement>(null)

  const getOverlayTypeData = (type: OverlayType) => {
    return OVERLAY_TYPES.find(t => t.value === type)
  }

  // Color picker component
  const ColorPickerComponent = ({ color, onChange }: { color: string, onChange: (color: string) => void }) => {
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
        alpha={false}
        hideInput={["hsv"]}
      />
    )
  }

  // Image upload handler
  const handleImageUpload = (position: GridPosition, file: File) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      const imageUrl = e.target?.result as string
      onUpdateOverlay(position, { imageUrl })
    }
    reader.readAsDataURL(file)
  }

  if (Object.entries(overlayPositions).length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-grey-light/60">No overlays configured yet.</p>
        <p className="text-grey-light/40 text-sm mt-1">
          Click on grid positions above to add overlays.
        </p>
      </div>
    )
  }

  return (
    <div ref={configRef} className="space-y-3">
      {Object.entries(overlayPositions).map(([position, overlay]) => {
        const typeData = getOverlayTypeData(overlay.type)
        return (
          <div 
            key={position} 
            className="space-y-3"
          >
            <div className="flex items-center space-x-2">
              <Badge 
                variant="secondary"
                className="bg-cyan/20 text-cyan border-cyan/30 text-xs"
              >
                {typeData?.label}
              </Badge>
            </div>
            
            <div className="grid grid-cols-2 gap-3">
              {/* Text Size */}
              <div className="space-y-1">
                <Label className="text-white text-xs">Size</Label>
                <NumberInput
                  value={overlay.textSize}
                  onChange={(value) => onUpdateOverlay(position as GridPosition, { textSize: value })}
                  min={8}
                  max={72}
                  className="bg-blue/20 border-purple-muted/50 focus:border-pink/50 h-8 text-xs"
                />
              </div>
              
              {/* Text Color */}
              <div className="space-y-1">
                <Label className="text-white text-xs">Color</Label>
                <Popover>
                  <PopoverTrigger asChild>
                    <div className="flex items-center space-x-1 cursor-pointer">
                      <div
                        className="w-8 h-8 rounded border-2 border-purple-muted/50"
                        style={{ backgroundColor: overlay.textColor }}
                      />
                      <Input
                        value={overlay.textColor}
                        onChange={(e) => onUpdateOverlay(position as GridPosition, { textColor: e.target.value })}
                        className="flex-1 text-xs bg-blue/20 border-purple-muted/50 focus:border-pink/50 text-white h-8"
                        placeholder="#FFFFFF"
                      />
                    </div>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0 bg-black border-purple-muted/50">
                    <ColorPickerComponent 
                      color={overlay.textColor}
                      onChange={(color) => onUpdateOverlay(position as GridPosition, { textColor: color })}
                    />
                  </PopoverContent>
                </Popover>
              </div>


              {/* Custom Text Field */}
              {overlay.type === "custom_text" && (
                <div className="space-y-1 col-span-2">
                  <Label className="text-white text-xs">Custom Text</Label>
                  <Input
                    value={overlay.customText || ""}
                    onChange={(e) => onUpdateOverlay(position as GridPosition, { customText: e.target.value })}
                    placeholder="Enter your custom text..."
                    className="bg-blue/20 border-purple-muted/50 focus:border-pink/50 text-white h-8 text-xs"
                  />
                </div>
              )}

              {/* Date Format for date/time overlays */}
              {(overlay.type.includes("date") || overlay.type.includes("time")) && (
                <div className="space-y-1 col-span-2">
                  <Label className="text-white text-xs">Date Format</Label>
                  <Input
                    value={overlay.dateFormat || "MM/dd/yyyy HH:mm"}
                    onChange={(e) => onUpdateOverlay(position as GridPosition, { dateFormat: e.target.value })}
                    placeholder="MM/dd/yyyy HH:mm"
                    className="bg-blue/20 border-purple-muted/50 focus:border-pink/50 text-white h-8 text-xs"
                  />
                  <p className="text-xs text-grey-light/60">
                    Use: MM/dd/yyyy, HH:mm, yyyy-MM-dd HH:mm:ss
                  </p>
                </div>
              )}

              {/* Image Upload for watermark/image overlays */}
              {(overlay.type === "watermark" || overlay.type === "image") && (
                <div className="space-y-1 col-span-2">
                  <Label className="text-white text-xs">Image Upload</Label>
                  
                  {/* Current Image Preview */}
                  {overlay.imageUrl && (
                    <div className="relative">
                      <div className="flex items-center space-x-2 p-2 bg-purple-muted/10 rounded border border-purple-muted/30">
                        <Image className="w-4 h-4 text-cyan" />
                        <span className="text-xs text-white truncate flex-1">Image uploaded</span>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => onUpdateOverlay(position as GridPosition, { imageUrl: undefined })}
                          className="h-6 w-6 p-0 hover:bg-failure/20 hover:text-failure"
                        >
                          <X className="w-3 h-3" />
                        </Button>
                      </div>
                      <div className="mt-2">
                        <img 
                          src={overlay.imageUrl} 
                          alt="Watermark preview" 
                          className="max-w-full h-16 object-contain rounded border border-purple-muted/30"
                        />
                      </div>
                    </div>
                  )}

                  {/* Upload Button */}
                  <div className="relative">
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => {
                        const file = e.target.files?.[0]
                        if (file) handleImageUpload(position as GridPosition, file)
                      }}
                      className="absolute inset-0 opacity-0 cursor-pointer"
                      id={`image-upload-${position}`}
                    />
                    <Button
                      variant="outline"
                      className="w-full h-8 text-xs border-purple-muted/50 text-cyan hover:bg-cyan/10 hover:border-cyan/50"
                      asChild
                    >
                      <label htmlFor={`image-upload-${position}`} className="cursor-pointer flex items-center space-x-2">
                        <Upload className="w-3 h-3" />
                        <span>{overlay.imageUrl ? 'Change Image' : 'Upload Image'}</span>
                      </label>
                    </Button>
                  </div>

                  {/* Image Scale */}
                  {overlay.imageUrl && (
                    <div className="space-y-1">
                      <ThemedSlider
                        label="Image Scale"
                        value={overlay.imageScale}
                        onChange={(value) => onUpdateOverlay(position as GridPosition, { imageScale: value })}
                        min={10}
                        max={200}
                        step={5}
                        unit="%"
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