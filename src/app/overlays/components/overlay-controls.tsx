// src/app/overlays/components/overlay-controls.tsx
"use client"

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { X } from "lucide-react"
import { OVERLAY_TYPES, GRID_POSITIONS } from "./overlay-constants"
import type { OverlayItem } from "@/hooks/use-overlay-presets"
import { DateTimeOverlayEditor } from "./date-time-overlay-editor"
import { WeatherOverlayEditor } from "./weather-overlay-editor"

interface AddOverlayModalProps {
  selectedPosition: string
  onAddOverlay: (position: string, type: string) => void
  onClose: () => void
}

export function AddOverlayModal({
  selectedPosition,
  onAddOverlay,
  onClose,
}: AddOverlayModalProps) {
  return (
    <Card className='border-purple/40 bg-gray-900/95 backdrop-blur-md shadow-2xl'>
      <CardHeader className='pb-3'>
        <CardTitle className='text-base flex items-center justify-between'>
          <span className='text-white'>
            Add Overlay -{" "}
            {GRID_POSITIONS.find((p) => p.id === selectedPosition)?.label}
          </span>
          <Button
            variant='ghost'
            size='sm'
            onClick={onClose}
            className='text-gray-400 hover:text-white hover:bg-red-500/20 p-1 h-6 w-6'
          >
            <X className='w-4 h-4' />
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent className='space-y-2 pt-0'>
        {OVERLAY_TYPES.map((type) => (
          <Button
            key={type.id}
            variant='outline'
            className='w-full justify-start h-auto p-3 hover:bg-purple/30 border-purple/40 hover:border-purple/60 transition-all duration-200'
            onClick={() => onAddOverlay(selectedPosition, type.id)}
          >
            <div className='flex items-center gap-3'>
              <type.icon className='w-5 h-5 text-purple shrink-0' />
              <div className='text-left'>
                <div className='font-medium text-white text-sm'>
                  {type.label}
                </div>
                <div className='text-xs text-gray-300 leading-tight'>
                  {type.description}
                </div>
              </div>
            </div>
          </Button>
        ))}
      </CardContent>
    </Card>
  )
}

interface OverlayEditorProps {
  overlay: OverlayItem
  selectedPosition: string
  onUpdateOverlay: (overlay: OverlayItem) => void
  onRemoveOverlay: (position: string) => void
}

export function OverlayEditor({
  overlay,
  selectedPosition,
  onUpdateOverlay,
  onRemoveOverlay,
}: OverlayEditorProps) {
  const updateOverlaySetting = (key: string, value: any) => {
    const updatedOverlay = {
      ...overlay,
      settings: { ...overlay.settings, [key]: value },
    }
    onUpdateOverlay(updatedOverlay)
  }

  const toggleOverlayEnabled = () => {
    const updatedOverlay = { ...overlay, enabled: !overlay.enabled }
    onUpdateOverlay(updatedOverlay)
  }

  return (
    <Card className='border-green/30 bg-green/5'>
      <CardHeader>
        <CardTitle className='text-sm flex items-center justify-between'>
          <div className='flex items-center gap-2'>
            <span>
              {OVERLAY_TYPES.find((t) => t.id === overlay.type)?.label}
            </span>
            <span className='text-xs text-green/70'>
              {GRID_POSITIONS.find((p) => p.id === selectedPosition)?.label}
            </span>
          </div>
          <Button
            variant='ghost'
            size='sm'
            onClick={() => onRemoveOverlay(selectedPosition)}
            className='text-red-400 hover:text-red-300 p-1'
          >
            <X className='w-4 h-4' />
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent className='space-y-3'>
        {overlay.type === "date_time" ? (
          <DateTimeOverlayEditor
            overlay={overlay}
            onUpdateOverlay={onUpdateOverlay}
          />
        ) : overlay.type === "weather" ? (
          <WeatherOverlayEditor
            overlay={overlay}
            onUpdateOverlay={onUpdateOverlay}
          />
        ) : (
          <div className='space-y-3'>
            {/* Common settings for other overlay types */}
            <div className='space-y-2'>
              <Label className='text-white text-xs font-medium'>
                Text Size
              </Label>
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
              <div className='text-xs text-gray-400'>
                {overlay.settings?.textSize || 16}px
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
        )}

        {/* Enabled Toggle - Always shown */}
        <div className='flex items-center justify-between pt-2 border-t border-gray-600/30'>
          <Label className='text-white text-sm font-medium'>Enabled</Label>
          <Switch
            checked={overlay.enabled}
            onCheckedChange={toggleOverlayEnabled}
            colorTheme='cyan'
          />
        </div>
      </CardContent>
    </Card>
  )
}
