// src/app/overlays/components/overlay-preset-editor.tsx
"use client"

import { useState, useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { NumberInput } from "@/components/ui/number-input"
import { ThemedSlider } from "@/components/ui/themed-slider"
import { SuperSwitch } from "@/components/ui/switch"
import { OverlayGrid } from "./overlay-grid"
import { OverlayConfig as OverlayConfigComponent } from "./overlay-config"
import { useCameras } from "@/hooks/use-cameras"
import {
  OVERLAY_TYPES,
  type GridPosition,
  type OverlayType,
} from "@/lib/overlay-presets-data"

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

interface OverlayConfig {
  overlayPositions: Partial<Record<GridPosition, OverlayItem>>
  globalOptions: {
    opacity: number
    dropShadow: number
    font: string
    xMargin: number
    yMargin: number
  }
}

interface OverlayPresetEditorProps {
  preset?: {
    id: number
    name: string
    description: string
    overlay_config: OverlayConfig
  } | null
  onSave: (name: string, description: string, config: OverlayConfig) => void
  onCancel: () => void
}

export function OverlayPresetEditor({
  preset,
  onSave,
  onCancel,
}: OverlayPresetEditorProps) {
  const [name, setName] = useState(preset?.name || "")
  const [description, setDescription] = useState(preset?.description || "")
  const [selectedPosition, setSelectedPosition] = useState<GridPosition | null>(
    null
  )
  const [selectedCamera, setSelectedCamera] = useState<string>("placeholder")
  const [backgroundImage, setBackgroundImage] = useState<string>(
    "/assets/placeholder-overlay.jpg"
  )
  const [livePreview, setLivePreview] = useState(false)

  const { cameras, loading: camerasLoading } = useCameras()
  const rightColumnRef = useRef<HTMLDivElement>(null)

  // Update background image when camera selection changes
  useEffect(() => {
    if (selectedCamera === "placeholder") {
      setBackgroundImage("/assets/placeholder-overlay.jpg")
    } else {
      // Use camera's latest image as background
      setBackgroundImage(`/api/cameras/${selectedCamera}/latest-image/small`)
    }
  }, [selectedCamera])

  const [overlayConfig, setOverlayConfig] = useState<OverlayConfig>(
    preset?.overlay_config || {
      overlayPositions: {},
      globalOptions: {
        opacity: 100,
        dropShadow: 0,
        font: "Arial",
        xMargin: 20,
        yMargin: 20,
      },
    }
  )

  const handleAddOverlay = (position: GridPosition, type: OverlayType) => {
    const newOverlay: OverlayItem = {
      type,
      textSize: 16,
      textColor: "#FFFFFF",
      backgroundOpacity: 0, // This will be ignored - using global backgroundOpacity
      imageScale: 100,
      ...(type === "custom_text" && { customText: "Enter text here" }),
      ...(type.includes("date") && { dateFormat: "MM/dd/yyyy HH:mm" }),
    }

    setOverlayConfig((prev) => ({
      ...prev,
      overlayPositions: {
        ...prev.overlayPositions,
        [position]: newOverlay,
      },
    }))
    
    // Auto-switch to the newly added overlay's settings
    setSelectedPosition(position)
  }

  const handleRemoveOverlay = (position: GridPosition) => {
    setOverlayConfig((prev) => {
      const newPositions = { ...prev.overlayPositions }
      delete newPositions[position]
      return {
        ...prev,
        overlayPositions: newPositions,
      }
    })
  }

  const handleUpdateOverlay = (
    position: GridPosition,
    updates: Partial<OverlayItem>
  ) => {
    setOverlayConfig((prev) => ({
      ...prev,
      overlayPositions: {
        ...prev.overlayPositions,
        [position]: {
          ...prev.overlayPositions[position]!,
          ...updates,
        },
      },
    }))
  }

  const handleUpdateGlobalOptions = (
    updates: Partial<OverlayConfig["globalOptions"]>
  ) => {
    setOverlayConfig((prev) => ({
      ...prev,
      globalOptions: {
        ...prev.globalOptions,
        ...updates,
      },
    }))
  }

  const handleSave = () => {
    if (name.trim()) {
      onSave(name, description, overlayConfig)
    }
  }

  return (
    <div className='space-y-6'>
      {/* Two Column Layout - Grid on Left, Config on Right */}
      <div className='grid grid-cols-1 lg:grid-cols-2 gap-8 min-h-[600px]'>
        {/* Left Column - Camera Dropdown and Overlay Grid */}
        <div className='space-y-4'>
          {/* Camera Selection */}
          <div className='space-y-2'>
            <Label className='text-white'>Preview Camera</Label>
            <Select value={selectedCamera} onValueChange={setSelectedCamera}>
              <SelectTrigger className='bg-blue/20 border-purple-muted/50 text-white'>
                <SelectValue />
              </SelectTrigger>
              <SelectContent className='bg-black border-purple-muted/50'>
                <SelectItem value='placeholder'>Placeholder Image</SelectItem>
                {!camerasLoading &&
                  cameras?.map((camera) => (
                    <SelectItem key={camera.id} value={camera.id.toString()}>
                      {camera.name}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>

          {/* Live Preview Toggle */}
          <div className='flex items-center justify-between'>
            <Label className='text-white text-sm'>Live Preview</Label>
            <SuperSwitch
              checked={livePreview}
              onCheckedChange={setLivePreview}
              colorTheme="cyan"
            />
          </div>

          {/* Preview Container - 16:9 aspect ratio */}
          <div
            className='relative rounded-lg overflow-hidden border-2 border-purple-muted/30 w-full aspect-video'
            style={{
              backgroundImage: `url(${backgroundImage})`,
              backgroundSize: "cover",
              backgroundPosition: "center",
              backgroundRepeat: "no-repeat",
              position: "relative", // Ensure this is the positioning context
            }}
          >
            {/* Dark overlay to make content visible when not in live preview */}
            {!livePreview && <div className='absolute inset-0 bg-black/60'></div>}
            
            {/* Margin Guidelines - Highest z-index */}
            <div 
              className='absolute border-2 border-dashed border-yellow-400/80 z-50 pointer-events-none'
              style={{
                top: `${overlayConfig.globalOptions.yMargin}px`,
                left: `${overlayConfig.globalOptions.xMargin}px`,
                right: `${overlayConfig.globalOptions.xMargin}px`,
                bottom: `${overlayConfig.globalOptions.yMargin}px`,
              }}
            ></div>
            
            <OverlayGrid
              overlayPositions={overlayConfig.overlayPositions}
              selectedPosition={selectedPosition}
              onPositionSelect={setSelectedPosition}
              onAddOverlay={handleAddOverlay}
              onRemoveOverlay={handleRemoveOverlay}
              livePreview={livePreview}
              globalOptions={overlayConfig.globalOptions}
            />
          </div>
        </div>

        {/* Right Column - Sticky Preset Info, Global Settings, and Selected Overlay Configuration */}
        <div ref={rightColumnRef} className='sticky top-0 space-y-4 max-h-[600px] overflow-y-auto pr-2'>
          {/* Compact Basic Information */}
          <div className='space-y-3 p-4 bg-purple/10 rounded-lg border border-purple/20'>
            <h4 className='text-sm font-medium text-white'>Preset Information</h4>
            <div className='space-y-2'>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder='Preset name...'
                className='bg-blue/20 border-purple-muted/50 focus:border-pink/50 text-white text-sm h-8'
              />
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder='Description...'
                className='bg-blue/20 border-purple-muted/50 focus:border-pink/50 text-white text-sm h-8'
              />
            </div>
          </div>

          {/* Compact Global Settings */}
          <div className='space-y-3 p-4 bg-purple/10 rounded-lg border border-purple/20'>
            <h4 className='text-sm font-medium text-white'>Global Settings</h4>
            <div className='grid grid-cols-2 gap-3'>
              <div className='space-y-1'>
                <Label className='text-white text-xs'>Font</Label>
                <Select
                  value={overlayConfig.globalOptions.font}
                  onValueChange={(value) =>
                    handleUpdateGlobalOptions({ font: value })
                  }
                >
                  <SelectTrigger className='bg-blue/20 border-purple-muted/50 text-white h-8 text-xs'>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className='bg-black border-purple-muted/50'>
                    <SelectItem value='Arial'>Arial</SelectItem>
                    <SelectItem value='Helvetica'>Helvetica</SelectItem>
                    <SelectItem value='Times New Roman'>Times New Roman</SelectItem>
                    <SelectItem value='Courier'>Courier</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className='space-y-1 col-span-2'>
                <ThemedSlider
                  label='Opacity'
                  value={overlayConfig.globalOptions.opacity}
                  onChange={(value) =>
                    handleUpdateGlobalOptions({ opacity: value })
                  }
                  max={100}
                  step={5}
                  unit='%'
                />
              </div>

              <div className='space-y-1'>
                <Label className='text-white text-xs'>X Margin</Label>
                <NumberInput
                  value={overlayConfig.globalOptions.xMargin}
                  onChange={(value) =>
                    handleUpdateGlobalOptions({ xMargin: value })
                  }
                  min={0}
                  max={200}
                  className='bg-blue/20 border-purple-muted/50 focus:border-pink/50 h-8 text-xs'
                />
              </div>

              <div className='space-y-1'>
                <Label className='text-white text-xs'>Y Margin</Label>
                <NumberInput
                  value={overlayConfig.globalOptions.yMargin}
                  onChange={(value) =>
                    handleUpdateGlobalOptions({ yMargin: value })
                  }
                  min={0}
                  max={200}
                  className='bg-blue/20 border-purple-muted/50 focus:border-pink/50 h-8 text-xs'
                />
              </div>

              <div className='space-y-1 col-span-2'>
                <ThemedSlider
                  label='Drop Shadow'
                  value={overlayConfig.globalOptions.dropShadow}
                  onChange={(value) =>
                    handleUpdateGlobalOptions({ dropShadow: value })
                  }
                  max={10}
                  step={1}
                  unit='px'
                />
              </div>
            </div>
          </div>

          {/* Selected Overlay Configuration */}
          {selectedPosition && overlayConfig.overlayPositions[selectedPosition] && (
            <div className='space-y-3 p-4 bg-cyan/10 rounded-lg border border-cyan/20 transition-all duration-300'>
              <h4 className='text-sm font-medium text-cyan'>
                {selectedPosition.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())} Overlay Settings
              </h4>
              <OverlayConfigComponent
                overlayPositions={{ [selectedPosition]: overlayConfig.overlayPositions[selectedPosition] }}
                onUpdateOverlay={handleUpdateOverlay}
                selectedPosition={selectedPosition}
              />
            </div>
          )}

          {/* Instruction Text */}
          {!selectedPosition && (
            <div className='p-4 bg-purple-muted/10 rounded-lg border border-purple-muted/20'>
              <p className='text-xs text-grey-light/60 text-center'>
                Click on an overlay position to configure its settings
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className='flex justify-end space-x-3 pt-4 border-t border-purple-muted/30'>
        <Button
          variant='outline'
          onClick={onCancel}
          className='border-purple-muted/50 text-grey-light hover:bg-purple-muted/20 hover:border-purple-muted hover:text-white'
        >
          Cancel
        </Button>
        <Button
          onClick={handleSave}
          disabled={!name.trim()}
          className='bg-gradient-to-r from-purple to-cyan hover:from-purple/90 hover:to-cyan/90 text-white font-medium'
        >
          Save Preset
        </Button>
      </div>
    </div>
  )
}
