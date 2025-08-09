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
import type {
  OverlayConfig,
  OverlayItem,
  GlobalSettings,
} from "@/hooks/use-overlay-presets"

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
      overlayItems: [],
      globalSettings: {
        opacity: 100,
        dropShadow: 0,
        font: "Arial",
        xMargin: 20,
        yMargin: 20,
        backgroundColor: "rgba(0,0,0,0.5)",
        backgroundOpacity: 50,
        fillColor: "#ffffff",
      },
    }
  )

  // Helper functions to work with overlay items
  const getOverlayAtPosition = (
    position: GridPosition
  ): OverlayItem | undefined => {
    return overlayConfig.overlayItems.find((item) => item.position === position)
  }

  const hasOverlayAtPosition = (position: GridPosition): boolean => {
    return overlayConfig.overlayItems.some((item) => item.position === position)
  }

  const handleAddOverlay = (position: GridPosition, type: OverlayType) => {
    const newOverlay: OverlayItem = {
      id: `${type}_${Date.now()}`,
      type: type as any, // Type mismatch will be resolved by updating interfaces
      position: position,
      enabled: true,
      settings: {
        textSize: 16,
        textColor: "#FFFFFF",
        backgroundOpacity: 0, // This will be ignored - using global backgroundOpacity
        imageScale: 100,
        ...(type === "custom_text" && { customText: "Enter text here" }),
        ...(type.includes("date") && { dateFormat: "MM/dd/yyyy HH:mm" }),
      },
    }

    setOverlayConfig((prev) => ({
      ...prev,
      overlayItems: [...prev.overlayItems, newOverlay],
    }))

    // Auto-switch to the newly added overlay's settings
    setSelectedPosition(position)
  }

  const handleRemoveOverlay = (position: GridPosition) => {
    setOverlayConfig((prev) => ({
      ...prev,
      overlayItems: prev.overlayItems.filter(
        (item) => item.position !== position
      ),
    }))
  }

  const handleUpdateOverlay = (
    position: GridPosition,
    updates: Partial<OverlayItem>
  ) => {
    setOverlayConfig((prev) => ({
      ...prev,
      overlayItems: prev.overlayItems.map((item) =>
        item.position === position ? { ...item, ...updates } : item
      ),
    }))
  }

  const handleUpdateGlobalSettings = (updates: Partial<GlobalSettings>) => {
    setOverlayConfig((prev) => ({
      ...prev,
      globalSettings: {
        ...prev.globalSettings,
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
              colorTheme='cyan'
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
            {!livePreview && (
              <div className='absolute inset-0 bg-black/60'></div>
            )}

            {/* Margin Guidelines - Highest z-index */}
            <div
              className='absolute border-2 border-dashed border-yellow-400/80 z-50 pointer-events-none'
              style={{
                top: `${overlayConfig.globalSettings.yMargin}px`,
                left: `${overlayConfig.globalSettings.xMargin}px`,
                right: `${overlayConfig.globalSettings.xMargin}px`,
                bottom: `${overlayConfig.globalSettings.yMargin}px`,
              }}
            ></div>

            <OverlayGrid
              overlayItems={overlayConfig.overlayItems}
              selectedItemId={
                selectedPosition
                  ? getOverlayAtPosition(selectedPosition)?.id || null
                  : null
              }
              onItemSelect={(itemId) => {
                // Find the position of the selected item
                const item = overlayConfig.overlayItems.find(
                  (i) => i.id === itemId
                )
                if (item) setSelectedPosition(item.position as GridPosition)
              }}
              onAddOverlay={handleAddOverlay}
              onRemoveOverlay={(itemId) => {
                // Find the position of the item to remove
                const item = overlayConfig.overlayItems.find(
                  (i) => i.id === itemId
                )
                if (item) handleRemoveOverlay(item.position as GridPosition)
              }}
              livePreview={livePreview}
              globalSettings={overlayConfig.globalSettings}
            />
          </div>
        </div>

        {/* Right Column - Sticky Preset Info, Global Settings, and Selected Overlay Configuration */}
        <div
          ref={rightColumnRef}
          className='sticky top-0 space-y-4 max-h-[600px] overflow-y-auto pr-2'
        >
          {/* Compact Basic Information */}
          <div className='space-y-3 p-4 bg-purple/10 rounded-lg border border-purple/20'>
            <h4 className='text-sm font-medium text-white'>
              Preset Information
            </h4>
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
                  value={overlayConfig.globalSettings.font}
                  onValueChange={(value) =>
                    handleUpdateGlobalSettings({ font: value })
                  }
                >
                  <SelectTrigger className='bg-blue/20 border-purple-muted/50 text-white h-8 text-xs'>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className='bg-black border-purple-muted/50'>
                    <SelectItem value='Arial'>Arial</SelectItem>
                    <SelectItem value='Helvetica'>Helvetica</SelectItem>
                    <SelectItem value='Times New Roman'>
                      Times New Roman
                    </SelectItem>
                    <SelectItem value='Courier'>Courier</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className='space-y-1 col-span-2'>
                <ThemedSlider
                  label='Opacity'
                  value={overlayConfig.globalSettings.opacity}
                  onChange={(value) =>
                    handleUpdateGlobalSettings({ opacity: value })
                  }
                  max={100}
                  step={5}
                  unit='%'
                />
              </div>

              <div className='space-y-1'>
                <Label className='text-white text-xs'>X Margin</Label>
                <NumberInput
                  value={overlayConfig.globalSettings.xMargin}
                  onChange={(value) =>
                    handleUpdateGlobalSettings({ xMargin: value })
                  }
                  min={0}
                  max={200}
                  className='bg-blue/20 border-purple-muted/50 focus:border-pink/50 h-8 text-xs'
                />
              </div>

              <div className='space-y-1'>
                <Label className='text-white text-xs'>Y Margin</Label>
                <NumberInput
                  value={overlayConfig.globalSettings.yMargin}
                  onChange={(value) =>
                    handleUpdateGlobalSettings({ yMargin: value })
                  }
                  min={0}
                  max={200}
                  className='bg-blue/20 border-purple-muted/50 focus:border-pink/50 h-8 text-xs'
                />
              </div>

              <div className='space-y-1 col-span-2'>
                <ThemedSlider
                  label='Drop Shadow'
                  value={overlayConfig.globalSettings.dropShadow}
                  onChange={(value) =>
                    handleUpdateGlobalSettings({ dropShadow: value })
                  }
                  max={10}
                  step={1}
                  unit='px'
                />
              </div>
            </div>
          </div>

          {/* Selected Overlay Configuration */}
          {selectedPosition && getOverlayAtPosition(selectedPosition) && (
            <div className='space-y-3 p-4 bg-cyan/10 rounded-lg border border-cyan/20 transition-all duration-300'>
              <h4 className='text-sm font-medium text-cyan'>
                {selectedPosition
                  .replace("_", " ")
                  .replace(/\b\w/g, (l) => l.toUpperCase())}{" "}
                Overlay Settings
              </h4>
              <OverlayConfigComponent
                overlayItems={[getOverlayAtPosition(selectedPosition)!]}
                onUpdateOverlay={(itemId, updates) => {
                  handleUpdateOverlay(selectedPosition, updates)
                }}
                selectedItemId={getOverlayAtPosition(selectedPosition)?.id}
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
