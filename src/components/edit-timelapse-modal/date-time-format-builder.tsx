// src/components/edit-timelapse-modal/date-time-format-builder.tsx
"use client"

import { useState, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { Input } from "@/components/ui/input"
import { Calendar, GripVertical } from "lucide-react"
import { cn } from "@/lib/utils"
import { formatDateTime } from "@/utils/date-format-utils"

interface DateTimeFormatBuilderProps {
  overlay: {
    enabled: boolean
    settings?: {
      dateFormat?: string
      textSize?: number
      enableBackground?: boolean
      enabled?: boolean
    }
  }
  onSettingsChange: (settings: any) => void
  onToggle: () => void
}

interface FormatBadge {
  id: string
  label: string
  example: string
  description: string
}

const formatBadges: FormatBadge[] = [
  { id: "YYYY", label: "YYYY", example: "2025", description: "4-digit year" },
  { id: "YY", label: "YY", example: "25", description: "2-digit year" },
  { id: "MM", label: "MM", example: "07", description: "2-digit month" },
  { id: "MMM", label: "MMM", example: "Jul", description: "3-letter month" },
  { id: "MMMM", label: "MMMM", example: "July", description: "Full month name" },
  { id: "DD", label: "DD", example: "20", description: "2-digit day" },
  { id: "D", label: "D", example: "20", description: "Day of month" },
  { id: "dddd", label: "dddd", example: "Sunday", description: "Full day name" },
  { id: "ddd", label: "ddd", example: "Sun", description: "3-letter day" },
  { id: "HH", label: "HH", example: "14", description: "24-hour (00-23)" },
  { id: "hh", label: "hh", example: "02", description: "12-hour (01-12)" },
  { id: "h", label: "h", example: "2", description: "12-hour (1-12)" },
  { id: "mm", label: "mm", example: "32", description: "Minutes (00-59)" },
  { id: "ss", label: "ss", example: "15", description: "Seconds (00-59)" },
  { id: "A", label: "A", example: "PM", description: "AM/PM uppercase" },
  { id: "a", label: "a", example: "pm", description: "am/pm lowercase" },
]

export function DateTimeFormatBuilder({ overlay, onSettingsChange, onToggle }: DateTimeFormatBuilderProps) {
  const [currentFormat, setCurrentFormat] = useState(overlay.settings?.dateFormat || "YYYY-MM-DD HH:mm:ss")
  const [draggedBadge, setDraggedBadge] = useState<FormatBadge | null>(null)
  const [hoveredBadge, setHoveredBadge] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Use shared formatting utility
  const formatPreview = formatDateTime

  const handleFormatChange = (newFormat: string) => {
    setCurrentFormat(newFormat)
    onSettingsChange({ dateFormat: newFormat })
  }

  const handleDragStart = (badge: FormatBadge) => {
    setDraggedBadge(badge)
  }

  const handleDragEnd = () => {
    setDraggedBadge(null)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    if (!draggedBadge || !inputRef.current) return

    const input = inputRef.current
    const cursorPos = input.selectionStart || 0
    const newFormat = 
      currentFormat.slice(0, cursorPos) + 
      draggedBadge.label + 
      currentFormat.slice(cursorPos)
    
    handleFormatChange(newFormat)
    
    // Set cursor after inserted badge
    setTimeout(() => {
      input.focus()
      input.setSelectionRange(cursorPos + draggedBadge.label.length, cursorPos + draggedBadge.label.length)
    }, 0)
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-2">
        <Calendar className="w-4 h-4 text-cyan" />
        <Label className="text-white text-sm font-medium">Date & Time</Label>
      </div>
      
      {/* Live Preview */}
      <div className="space-y-2">
        <Label className="text-white text-xs font-medium">Preview</Label>
        <div className="p-2 bg-gray-800/50 border border-gray-600/50 rounded text-white text-sm font-mono">
          {formatPreview(currentFormat)}
        </div>
      </div>
      
      {/* Format Input Field */}
      <div className="space-y-2">
        <Label className="text-white text-xs font-medium">Format Builder</Label>
        <Input
          ref={inputRef}
          value={currentFormat}
          onChange={(e) => handleFormatChange(e.target.value)}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          placeholder="Drag badges here or type..."
          className="bg-gray-800/50 border-gray-600/50 text-white placeholder-gray-400 font-mono"
        />
        <div className="text-xs text-gray-400">
          Drag format badges below or type manually (-, :, spaces, etc.)
        </div>
      </div>
      
      {/* Format Badges */}
      <div className="space-y-2">
        <Label className="text-white text-xs font-medium">Format Badges</Label>
        <div className="grid grid-cols-3 gap-1 max-h-32 overflow-y-auto">
          {formatBadges.map((badge) => (
            <div
              key={badge.id}
              draggable
              onDragStart={() => handleDragStart(badge)}
              onDragEnd={handleDragEnd}
              onMouseEnter={() => setHoveredBadge(badge.id)}
              onMouseLeave={() => setHoveredBadge(null)}
              className={cn(
                "relative flex items-center gap-1 p-1 rounded border cursor-grab transition-all duration-200",
                "bg-cyan/10 border-cyan/30 text-cyan text-xs font-mono",
                "hover:bg-cyan/20 hover:border-cyan/50",
                "active:cursor-grabbing"
              )}
            >
              <GripVertical className="w-3 h-3 text-cyan/60" />
              <span>{badge.label}</span>
              
              {/* Hover Tooltip */}
              {hoveredBadge === badge.id && (
                <div className="absolute bottom-full left-0 mb-1 z-10 p-2 bg-gray-900 border border-gray-600 rounded shadow-lg">
                  <div className="text-white text-xs font-medium">{badge.example}</div>
                  <div className="text-gray-400 text-xs">{badge.description}</div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
      
      {/* Quick Presets */}
      <div className="space-y-2">
        <Label className="text-white text-xs font-medium">Quick Presets</Label>
        <div className="grid grid-cols-1 gap-1">
          {[
            "YYYY-MM-DD HH:mm:ss",
            "MM/DD/YYYY h:mm A",
            "DD/MM/YYYY HH:mm",
            "MMM DD, YYYY",
            "dddd, MMMM DD"
          ].map((preset) => (
            <Button
              key={preset}
              size="sm"
              variant="outline"
              onClick={() => handleFormatChange(preset)}
              className={cn(
                "text-xs h-7 justify-between font-mono",
                currentFormat === preset 
                  ? "bg-cyan/20 border-cyan/50 text-white" 
                  : "border-gray-500 text-gray-400 hover:bg-gray-700/50"
              )}
            >
              <span>{preset}</span>
              <span className="text-cyan text-xs">{formatPreview(preset)}</span>
            </Button>
          ))}
        </div>
      </div>
      
      {/* Font Size */}
      <div className="space-y-2">
        <Label className="text-white text-xs font-medium">Font Size</Label>
        <Slider
          value={[overlay.settings?.textSize || 16]}
          onValueChange={(value) => {
            onSettingsChange({ textSize: value[0] })
          }}
          max={24}
          min={10}
          step={1}
          className="w-full"
        />
        <div className="text-xs text-gray-400">{overlay.settings?.textSize || 16}px</div>
      </div>

      {/* Enable Background */}
      <div className="flex items-center justify-between">
        <Label className="text-white text-xs font-medium">Enable Background</Label>
        <Switch
          checked={overlay.settings?.enableBackground || false}
          onCheckedChange={(checked) => {
            onSettingsChange({ enableBackground: checked })
          }}
          colorTheme="cyan"
          size="sm"
        />
      </div>
      
      {/* Enabled Toggle */}
      <div className="flex items-center justify-between pt-2 border-t border-gray-600/30">
        <Label className="text-white text-sm font-medium">Enabled</Label>
        <Switch
          checked={overlay.enabled}
          onCheckedChange={onToggle}
          colorTheme="cyan"
        />
      </div>
    </div>
  )
}