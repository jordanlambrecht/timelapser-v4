// src/components/overlay-config/timelapse-name-config.tsx
"use client"

import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { FileText } from "lucide-react"

interface TimelapseNameConfigProps {
  settings: {
    textSize?: number
    enableBackground?: boolean
    enabled?: boolean
  }
  timelapseTitle?: string
  onChange: (settings: Partial<TimelapseNameConfigProps["settings"]>) => void
}

export function TimelapseNameConfig({ 
  settings, 
  timelapseTitle = "Timelapse Name", 
  onChange 
}: TimelapseNameConfigProps) {
  return (
    <div className='space-y-3'>
      <div className='flex items-center gap-2 mb-2'>
        <FileText className='w-4 h-4 text-cyan' />
        <Label className='text-white text-sm font-medium'>
          Timelapse Name
        </Label>
      </div>

      {/* Preview */}
      <div className='space-y-2'>
        <Label className='text-white text-xs font-medium'>Preview</Label>
        <div className='p-2 bg-gray-800/50 border border-gray-600/50 rounded text-white text-sm'>
          {timelapseTitle}
        </div>
      </div>

      {/* Text Size */}
      <div className='space-y-2'>
        <Label className='text-white text-xs font-medium'>
          Text Size
        </Label>
        <div className='flex items-center gap-2'>
          <Slider
            value={[settings.textSize || 16]}
            onValueChange={(value) => onChange({ textSize: value[0] })}
            max={72}
            min={8}
            step={1}
            className='flex-1'
          />
          <span className='text-white text-xs w-8 text-right'>
            {settings.textSize || 16}px
          </span>
        </div>
      </div>

      {/* Enable Background */}
      <div className='flex items-center justify-between'>
        <Label className='text-white text-xs font-medium'>
          Enable Background
        </Label>
        <Switch
          checked={settings.enableBackground || false}
          onCheckedChange={(checked) => onChange({ enableBackground: checked })}
          colorTheme='cyan'
        />
      </div>
    </div>
  )
}
