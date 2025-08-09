// src/components/overlay-config/day-number-config.tsx
"use client"

import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { Activity } from "lucide-react"

interface DayNumberConfigProps {
  settings: {
    textSize?: number
    leadingZeros?: boolean
    hidePrefix?: boolean
    enableBackground?: boolean
    enabled?: boolean
  }
  onChange: (settings: Partial<DayNumberConfigProps["settings"]>) => void
}

export function DayNumberConfig({ settings, onChange }: DayNumberConfigProps) {
  return (
    <div className='space-y-3'>
      <div className='flex items-center gap-2 mb-2'>
        <Activity className='w-4 h-4 text-purple' />
        <Label className='text-white text-sm font-medium'>Day Counter</Label>
      </div>

      {/* Text Size */}
      <div className='space-y-2'>
        <Label className='text-white text-xs font-medium'>Text Size</Label>
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

      {/* Leading Zeros */}
      <div className='flex items-center justify-between'>
        <Label className='text-white text-xs font-medium'>Leading Zeros</Label>
        <Switch
          checked={settings.leadingZeros || false}
          onCheckedChange={(checked) => onChange({ leadingZeros: checked })}
          colorTheme='cyan'
        />
      </div>

      {/* Hide Prefix */}
      <div className='flex items-center justify-between'>
        <Label className='text-white text-xs font-medium'>Hide Prefix</Label>
        <Switch
          checked={settings.hidePrefix || false}
          onCheckedChange={(checked) => onChange({ hidePrefix: checked })}
          colorTheme='cyan'
        />
      </div>
      <div className='text-xs text-gray-400 -mt-1'>
        Show "01" instead of "Day 01"
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
