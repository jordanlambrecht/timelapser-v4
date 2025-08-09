// src/components/overlay-config/frame-number-config.tsx
"use client"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { Hash } from "lucide-react"

interface FrameNumberConfigProps {
  settings: {
    prefix?: string
    textSize?: number
    leadingZeros?: boolean
    enableBackground?: boolean
    enabled?: boolean
  }
  onChange: (settings: Partial<FrameNumberConfigProps["settings"]>) => void
}

export function FrameNumberConfig({
  settings,
  onChange,
}: FrameNumberConfigProps) {
  return (
    <div className='space-y-3'>
      <div className='flex items-center gap-2 mb-2'>
        <Hash className='w-4 h-4 text-pink' />
        <Label className='text-white text-sm font-medium'>Frame Number</Label>
      </div>

      {/* Prefix */}
      <div className='space-y-2'>
        <Label className='text-white text-xs font-medium'>Prefix</Label>
        <Input
          value={settings.prefix || "Frame"}
          onChange={(e) => onChange({ prefix: e.target.value })}
          placeholder='Frame'
          className='bg-gray-800/50 border-gray-600/50 text-white placeholder-gray-400'
        />
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
          colorTheme='pink'
        />
      </div>

      {/* Enable Background */}
      <div className='flex items-center justify-between'>
        <Label className='text-white text-xs font-medium'>
          Enable Background
        </Label>
        <Switch
          checked={settings.enableBackground || false}
          onCheckedChange={(checked) => onChange({ enableBackground: checked })}
          colorTheme='pink'
        />
      </div>
    </div>
  )
}
