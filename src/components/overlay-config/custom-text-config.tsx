// src/components/overlay-config/custom-text-config.tsx
"use client"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { Type } from "lucide-react"

interface CustomTextConfigProps {
  settings: {
    customText?: string
    textSize?: number
    enableBackground?: boolean
    enabled?: boolean
  }
  onChange: (settings: Partial<CustomTextConfigProps["settings"]>) => void
}

export function CustomTextConfig({
  settings,
  onChange,
}: CustomTextConfigProps) {
  return (
    <div className='space-y-3'>
      <div className='flex items-center gap-2 mb-2'>
        <Type className='w-4 h-4 text-pink' />
        <Label className='text-white text-sm font-medium'>Custom Text</Label>
      </div>

      {/* Text Input */}
      <div className='space-y-2'>
        <Label className='text-white text-xs font-medium'>Custom Text</Label>
        <Input
          value={settings.customText || ""}
          onChange={(e) => onChange({ customText: e.target.value })}
          placeholder='Enter custom text...'
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
