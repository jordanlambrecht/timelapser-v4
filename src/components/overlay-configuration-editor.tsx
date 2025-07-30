// src/components/overlay-configuration-editor.tsx
"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"
import { 
  Settings, 
  Type, 
  Move, 
  Eye,
  Plus,
  Trash2,
  Save,
  RotateCcw
} from "lucide-react"
import type { OverlayPreset } from "@/hooks/use-overlay-presets"

interface OverlayPosition {
  type: string
  textSize: number
  position: {
    x: string
    y: string
  }
  color?: string
  enabled?: boolean
}

interface OverlayConfig {
  overlayPositions: Record<string, OverlayPosition>
  globalOptions: {
    opacity: number
    dropShadow: number
    font: string
    xMargin: number
    yMargin: number
  }
}

interface OverlayConfigurationEditorProps {
  config?: OverlayConfig
  onChange: (config: OverlayConfig) => void
  onSave?: () => void
  onReset?: () => void
  onPreview?: () => void
  saving?: boolean
  className?: string
}

const OVERLAY_TYPES = [
  { value: "timestamp", label: "Timestamp" },
  { value: "camera_name", label: "Camera Name" },
  { value: "weather", label: "Weather Info" },
  { value: "custom_text", label: "Custom Text" },
  { value: "image_count", label: "Image Count" },
  { value: "date_only", label: "Date Only" },
  { value: "time_only", label: "Time Only" },
]

const FONT_OPTIONS = [
  { value: "dejavu", label: "DejaVu Sans" },
  { value: "liberation", label: "Liberation Sans" },
  { value: "arial", label: "Arial" },
  { value: "helvetica", label: "Helvetica" },
]

const POSITION_PRESETS = [
  { x: "left", y: "top", label: "Top Left" },
  { x: "center", y: "top", label: "Top Center" },
  { x: "right", y: "top", label: "Top Right" },
  { x: "left", y: "center", label: "Center Left" },
  { x: "center", y: "center", label: "Center" },
  { x: "right", y: "center", label: "Center Right" },
  { x: "left", y: "bottom", label: "Bottom Left" },
  { x: "center", y: "bottom", label: "Bottom Center" },
  { x: "right", y: "bottom", label: "Bottom Right" },
]

export function OverlayConfigurationEditor({
  config,
  onChange,
  onSave,
  onReset,
  onPreview,
  saving = false,
  className
}: OverlayConfigurationEditorProps) {
  const [currentConfig, setCurrentConfig] = useState<OverlayConfig>(
    config || {
      overlayPositions: {},
      globalOptions: {
        opacity: 85,
        dropShadow: 2,
        font: "dejavu",
        xMargin: 20,
        yMargin: 20
      }
    }
  )

  const handleGlobalOptionChange = (key: keyof OverlayConfig['globalOptions'], value: any) => {
    const newConfig = {
      ...currentConfig,
      globalOptions: {
        ...currentConfig.globalOptions,
        [key]: value
      }
    }
    setCurrentConfig(newConfig)
    onChange(newConfig)
  }

  const handleAddOverlay = () => {
    const newId = `overlay_${Date.now()}`
    const newConfig = {
      ...currentConfig,
      overlayPositions: {
        ...currentConfig.overlayPositions,
        [newId]: {
          type: "timestamp",
          textSize: 24,
          position: { x: "left", y: "top" },
          color: "#FFFFFF",
          enabled: true
        }
      }
    }
    setCurrentConfig(newConfig)
    onChange(newConfig)
  }

  const handleRemoveOverlay = (id: string) => {
    const { [id]: removed, ...remaining } = currentConfig.overlayPositions
    const newConfig = {
      ...currentConfig,
      overlayPositions: remaining
    }
    setCurrentConfig(newConfig)
    onChange(newConfig)
  }

  const handleOverlayChange = (id: string, key: string, value: any) => {
    const newConfig = {
      ...currentConfig,
      overlayPositions: {
        ...currentConfig.overlayPositions,
        [id]: {
          ...currentConfig.overlayPositions[id],
          [key]: value
        }
      }
    }
    setCurrentConfig(newConfig)
    onChange(newConfig)
  }

  const handlePositionChange = (id: string, axis: 'x' | 'y', value: string) => {
    const newConfig = {
      ...currentConfig,
      overlayPositions: {
        ...currentConfig.overlayPositions,
        [id]: {
          ...currentConfig.overlayPositions[id],
          position: {
            ...currentConfig.overlayPositions[id].position,
            [axis]: value
          }
        }
      }
    }
    setCurrentConfig(newConfig)
    onChange(newConfig)
  }

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Settings className="w-6 h-6 text-purple" />
          <h2 className="text-xl font-semibold">Overlay Configuration</h2>
        </div>
        <div className="flex items-center space-x-2">
          {onPreview && (
            <Button
              onClick={onPreview}
              variant="outline"
              size="sm"
              className="border-cyan/30 text-cyan hover:bg-cyan/10"
            >
              <Eye className="w-4 h-4 mr-2" />
              Preview
            </Button>
          )}
          {onReset && (
            <Button
              onClick={onReset}
              variant="outline"
              size="sm"
              className="border-gray-600 hover:border-gray-500"
            >
              <RotateCcw className="w-4 h-4 mr-2" />
              Reset
            </Button>
          )}
          {onSave && (
            <Button
              onClick={onSave}
              disabled={saving}
              className="bg-gradient-to-r from-purple to-cyan hover:from-purple/90 hover:to-cyan/90"
            >
              <Save className="w-4 h-4 mr-2" />
              {saving ? "Saving..." : "Save"}
            </Button>
          )}
        </div>
      </div>

      {/* Global Options */}
      <Card className="bg-gray-900/50 border-gray-700">
        <CardHeader>
          <CardTitle className="text-lg flex items-center space-x-2">
            <Settings className="w-5 h-5 text-cyan" />
            <span>Global Options</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid md:grid-cols-2 gap-6">
            {/* Font Selection */}
            <div className="space-y-2">
              <Label>Font Family</Label>
              <Select 
                value={currentConfig.globalOptions.font} 
                onValueChange={(value) => handleGlobalOptionChange('font', value)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {FONT_OPTIONS.map(font => (
                    <SelectItem key={font.value} value={font.value}>
                      {font.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Opacity */}
            <div className="space-y-2">
              <Label>Opacity: {currentConfig.globalOptions.opacity}%</Label>
              <Slider
                value={[currentConfig.globalOptions.opacity]}
                onValueChange={([value]) => handleGlobalOptionChange('opacity', value)}
                max={100}
                min={0}
                step={5}
                className="w-full"
              />
            </div>

            {/* Drop Shadow */}
            <div className="space-y-2">
              <Label>Drop Shadow: {currentConfig.globalOptions.dropShadow}px</Label>
              <Slider
                value={[currentConfig.globalOptions.dropShadow]}
                onValueChange={([value]) => handleGlobalOptionChange('dropShadow', value)}
                max={10}
                min={0}
                step={1}
                className="w-full"
              />
            </div>

            {/* Margins */}
            <div className="space-y-2">
              <Label>Margins</Label>
              <div className="flex space-x-2">
                <div>
                  <Input
                    type="number"
                    placeholder="X Margin"
                    value={currentConfig.globalOptions.xMargin}
                    onChange={(e) => handleGlobalOptionChange('xMargin', parseInt(e.target.value) || 0)}
                    className="w-20"
                  />
                </div>
                <div>
                  <Input
                    type="number"
                    placeholder="Y Margin"
                    value={currentConfig.globalOptions.yMargin}
                    onChange={(e) => handleGlobalOptionChange('yMargin', parseInt(e.target.value) || 0)}
                    className="w-20"
                  />
                </div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Overlay Elements */}
      <Card className="bg-gray-900/50 border-gray-700">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center space-x-2">
              <Type className="w-5 h-5 text-purple" />
              <span>Overlay Elements</span>
              <Badge variant="secondary" className="ml-2">
                {Object.keys(currentConfig.overlayPositions).length}
              </Badge>
            </CardTitle>
            <Button
              onClick={handleAddOverlay}
              size="sm"
              className="bg-gradient-to-r from-green-600 to-green-500 hover:from-green-700 hover:to-green-600"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Element
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {Object.keys(currentConfig.overlayPositions).length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Type className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>No overlay elements configured.</p>
              <p className="text-sm">Click "Add Element" to get started.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {Object.entries(currentConfig.overlayPositions).map(([id, overlay]) => (
                <Card key={id} className="bg-gray-800/50 border-gray-600">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center space-x-2">
                        <Switch
                          checked={overlay.enabled !== false}
                          onCheckedChange={(checked) => handleOverlayChange(id, 'enabled', checked)}
                        />
                        <Badge variant="outline">
                          {OVERLAY_TYPES.find(t => t.value === overlay.type)?.label || overlay.type}
                        </Badge>
                      </div>
                      <Button
                        onClick={() => handleRemoveOverlay(id)}
                        size="sm"
                        variant="ghost"
                        className="text-red-400 hover:text-red-300 hover:bg-red-500/20"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>

                    <div className="grid md:grid-cols-3 gap-4">
                      {/* Type */}
                      <div className="space-y-2">
                        <Label>Type</Label>
                        <Select 
                          value={overlay.type} 
                          onValueChange={(value) => handleOverlayChange(id, 'type', value)}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {OVERLAY_TYPES.map(type => (
                              <SelectItem key={type.value} value={type.value}>
                                {type.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Text Size */}
                      <div className="space-y-2">
                        <Label>Text Size: {overlay.textSize}px</Label>
                        <Slider
                          value={[overlay.textSize]}
                          onValueChange={([value]) => handleOverlayChange(id, 'textSize', value)}
                          max={72}
                          min={12}
                          step={2}
                          className="w-full"
                        />
                      </div>

                      {/* Position */}
                      <div className="space-y-2">
                        <Label>Position</Label>
                        <div className="grid grid-cols-2 gap-2">
                          <Select 
                            value={overlay.position.x} 
                            onValueChange={(value) => handlePositionChange(id, 'x', value)}
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="left">Left</SelectItem>
                              <SelectItem value="center">Center</SelectItem>
                              <SelectItem value="right">Right</SelectItem>
                            </SelectContent>
                          </Select>
                          <Select 
                            value={overlay.position.y} 
                            onValueChange={(value) => handlePositionChange(id, 'y', value)}
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="top">Top</SelectItem>
                              <SelectItem value="center">Center</SelectItem>
                              <SelectItem value="bottom">Bottom</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}