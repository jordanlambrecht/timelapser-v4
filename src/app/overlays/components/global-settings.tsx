// src/app/overlays/components/global-settings.tsx
"use client"

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Globe, ChevronRight } from "lucide-react"
import { cn } from "@/lib/utils"
import type { GlobalSettings } from "@/hooks/use-overlay-presets"

interface GlobalSettingsProps {
  globalSettings: GlobalSettings
  onSettingsChange: (settings: GlobalSettings) => void
  isExpanded: boolean
  onToggleExpanded: () => void
}

export function GlobalSettingsCard({
  globalSettings,
  onSettingsChange,
  isExpanded,
  onToggleExpanded,
}: GlobalSettingsProps) {
  const updateSettings = (updates: Partial<GlobalSettings>) => {
    onSettingsChange({ ...globalSettings, ...updates })
  }

  return (
    <Card className='border-gray-600/30'>
      <CardHeader className='pb-3'>
        <Button
          variant='ghost'
          onClick={onToggleExpanded}
          className='w-full justify-between p-3 h-auto bg-cyan/5 border border-cyan/20 rounded-lg hover:bg-cyan/10'
        >
          <div className='flex items-center gap-2'>
            <Globe className='w-4 h-4 text-cyan' />
            <span className='text-white font-medium'>Global Settings</span>
          </div>
          <ChevronRight
            className={cn(
              "w-4 h-4 text-cyan transition-transform",
              isExpanded && "rotate-90"
            )}
          />
        </Button>
      </CardHeader>

      {isExpanded && (
        <CardContent className='space-y-4'>
          {/* Margins */}
          <div className='space-y-2'>
            <Label className='text-white text-xs font-medium'>Margins</Label>
            <div className='flex items-center gap-2'>
              <div className='flex items-center gap-1'>
                <Label className='text-gray-400 text-xs'>X:</Label>
                <Input
                  type='number'
                  value={globalSettings.xMargin}
                  onChange={(e) =>
                    updateSettings({
                      xMargin: parseInt(e.target.value) || 0,
                    })
                  }
                  className='w-12 h-6 text-xs bg-gray-800/50 border-gray-600/50 text-white'
                />
              </div>
              <div className='flex items-center gap-1'>
                <Label className='text-gray-400 text-xs'>Y:</Label>
                <Input
                  type='number'
                  value={globalSettings.yMargin}
                  onChange={(e) =>
                    updateSettings({
                      yMargin: parseInt(e.target.value) || 0,
                    })
                  }
                  className='w-12 h-6 text-xs bg-gray-800/50 border-gray-600/50 text-white'
                />
              </div>
            </div>
          </div>

          {/* Opacity */}
          <div className='space-y-2'>
            <Label className='text-white text-xs font-medium'>Opacity</Label>
            <Slider
              value={[globalSettings.opacity]}
              onValueChange={(value) => updateSettings({ opacity: value[0] })}
              max={100}
              min={0}
              step={1}
              className='w-full'
            />
            <div className='text-xs text-gray-400'>
              {globalSettings.opacity}%
            </div>
          </div>

          {/* Drop Shadow */}
          <div className='space-y-2'>
            <Label className='text-white text-xs font-medium'>
              Drop Shadow
            </Label>
            <Slider
              value={[globalSettings.dropShadow]}
              onValueChange={(value) =>
                updateSettings({ dropShadow: value[0] })
              }
              max={100}
              min={0}
              step={1}
              className='w-full'
            />
            <div className='text-xs text-gray-400'>
              {globalSettings.dropShadow}%
            </div>
          </div>

          {/* Font Selection */}
          <div className='space-y-2'>
            <Label className='text-white text-xs font-medium'>Font</Label>
            <Select
              value={globalSettings.font}
              onValueChange={(value) => updateSettings({ font: value })}
            >
              <SelectTrigger className='bg-gray-800/50 border-gray-600/50 text-white'>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='Helvetica'>Helvetica</SelectItem>
                <SelectItem value='Arial'>Arial</SelectItem>
                <SelectItem value='Times New Roman'>Times New Roman</SelectItem>
                <SelectItem value='Courier New'>Courier New</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Background Settings */}
          <div className='space-y-3'>
            <Label className='text-white text-xs font-medium'>Background</Label>

            {/* Background Color */}
            <div className='space-y-2'>
              <Label className='text-gray-400 text-xs'>Background Color</Label>
              <div className='flex items-center gap-2'>
                <Input
                  type='color'
                  value={globalSettings.backgroundColor}
                  onChange={(e) =>
                    updateSettings({ backgroundColor: e.target.value })
                  }
                  className='w-12 h-8 p-0 border-0 bg-transparent cursor-pointer'
                />
                <Input
                  type='text'
                  value={globalSettings.backgroundColor}
                  onChange={(e) =>
                    updateSettings({ backgroundColor: e.target.value })
                  }
                  className='flex-1 h-8 text-xs bg-gray-800/50 border-gray-600/50 text-white'
                />
              </div>
            </div>

            {/* Background Opacity */}
            <div className='space-y-2'>
              <Label className='text-gray-400 text-xs'>
                Background Opacity
              </Label>
              <Slider
                value={[globalSettings.backgroundOpacity]}
                onValueChange={(value) =>
                  updateSettings({ backgroundOpacity: value[0] })
                }
                max={100}
                min={0}
                step={1}
                className='w-full'
              />
              <div className='text-xs text-gray-400'>
                {globalSettings.backgroundOpacity}%
              </div>
            </div>
          </div>

          {/* Fill Color */}
          <div className='space-y-2'>
            <Label className='text-white text-xs font-medium'>Fill Color</Label>
            <div className='flex items-center gap-2'>
              <Input
                type='color'
                value={globalSettings.fillColor}
                onChange={(e) => updateSettings({ fillColor: e.target.value })}
                className='w-12 h-8 p-0 border-0 bg-transparent cursor-pointer'
              />
              <Input
                type='text'
                value={globalSettings.fillColor}
                onChange={(e) => updateSettings({ fillColor: e.target.value })}
                className='flex-1 h-8 text-xs bg-gray-800/50 border-gray-600/50 text-white'
              />
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  )
}
