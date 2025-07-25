// src/components/timelapse-creation/slides/capture-interval-slide.tsx
"use client"

import { Button } from "@/components/ui/button"
import { NumberInput } from "@/components/ui/number-input"
import { Label } from "@/components/ui/label"
import { Camera, Timer, Zap } from "lucide-react"
import { cn } from "@/lib/utils"
import type { TimelapseForm } from "../timelapse-creation-modal"

interface CaptureIntervalSlideProps {
  form: TimelapseForm
  updateForm: (updates: Partial<TimelapseForm>) => void
}

const presets = [
  { label: "30s", value: 30, desc: "High detail" },
  { label: "1m", value: 60, desc: "Detailed" },
  { label: "5m", value: 300, desc: "Standard" },
  { label: "15m", value: 900, desc: "Moderate" },
  { label: "1h", value: 3600, desc: "Long-term" },
  { label: "2h", value: 7200, desc: "Longer-term" },
]

const formatInterval = (seconds: number) => {
  if (seconds < 60) {
    return `${seconds} second${seconds === 1 ? '' : 's'}`
  }
  
  if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    if (remainingSeconds === 0) {
      return `${minutes} minute${minutes === 1 ? '' : 's'}`
    }
    return `${minutes} min ${remainingSeconds} sec`
  }
  
  const hours = Math.floor(seconds / 3600)
  const remainingMinutes = Math.floor((seconds % 3600) / 60)
  const remainingSeconds = seconds % 60
  
  let result = `${hours} hour${hours === 1 ? '' : 's'}`
  if (remainingMinutes > 0) {
    result += ` ${remainingMinutes} min`
  }
  if (remainingSeconds > 0) {
    result += ` ${remainingSeconds} sec`
  }
  
  return result
}

export function CaptureIntervalSlide({
  form,
  updateForm,
}: CaptureIntervalSlideProps) {
  const handleIntervalChange = (value: number) => {
    // Validate input - must be a positive integer
    if (isNaN(value) || !isFinite(value)) {
      // If invalid, keep current value or default to 1
      updateForm({ captureInterval: form.captureInterval || 1 })
      return
    }
    
    // Ensure it's a positive integer
    const intValue = Math.max(1, Math.floor(Math.abs(value)))
    
    // Clamp value to 24 hours max (86400 seconds)
    const clampedValue = Math.min(intValue, 86400)
    updateForm({ captureInterval: clampedValue })
  }

  // Validation state
  const isValid = Number.isInteger(form.captureInterval) && 
                  form.captureInterval >= 1 && 
                  form.captureInterval <= 86400
  
  const errorMessage = !isValid 
    ? !Number.isInteger(form.captureInterval) || form.captureInterval < 1
      ? "Must be a positive integer (minimum 1 second)"
      : "Maximum interval is 24 hours (86400 seconds)"
    : null

  return (
    <div className="px-1 space-y-6">
      <div className="text-center">
        <h3 className="text-xl font-semibold text-white mb-2">Capture Interval</h3>
        <p className="text-grey-light/70">How often should images be captured?</p>
      </div>

      {/* Manual Input & Quick Presets Combined */}
      <div className="space-y-4">
        <div className="flex items-center space-x-2">
          <Timer className="w-4 h-4 text-cyan" />
          <Label className="text-white font-medium">Capture Interval</Label>
        </div>
        
        <div className={cn(
          "p-4 rounded-lg space-y-4 transition-all duration-300",
          isValid 
            ? "bg-cyan/5 border border-cyan/20" 
            : "bg-red-500/5 border border-red-500/30"
        )}>
          <div className="flex items-center justify-between">
            <Label className={cn("text-sm", isValid ? "text-cyan" : "text-red-400")}>
              Interval (seconds)
            </Label>
            <span className={cn("text-xs", isValid ? "text-cyan/70" : "text-red-400/70")}>
              {formatInterval(form.captureInterval)}
            </span>
          </div>
          
          <NumberInput
            value={form.captureInterval}
            onChange={handleIntervalChange}
            min={1}
            max={86400} // 24 hours
            step={1}
            variant="buttons"
            hideLabel={true}
            className={cn(
              "bg-black/20 text-white transition-all duration-300",
              isValid 
                ? "border-cyan/30 focus:border-cyan/50" 
                : "border-red-500/30 focus:border-red-500/50"
            )}
          />
          
          {/* Error Message */}
          {errorMessage && (
            <div className="flex items-center space-x-2 text-red-400 text-xs">
              <span>⚠️</span>
              <span>{errorMessage}</span>
            </div>
          )}
          
          {/* Quick Presets */}
          <div className="space-y-2">
            <Label className={cn("text-xs", isValid ? "text-cyan" : "text-red-400")}>
              Quick Presets:
            </Label>
            <div className="grid grid-cols-3 gap-2">
              {presets.map((preset) => (
                <Button
                  key={preset.value}
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => updateForm({ captureInterval: preset.value })}
                  className={cn(
                    "h-8 text-xs transition-all duration-300",
                    form.captureInterval === preset.value
                      ? "bg-purple/20 border-purple text-purple hover:bg-purple/30"
                      : "bg-black/20 border-purple-muted/30 text-grey-light hover:bg-purple-dark/20 hover:border-purple-muted hover:text-white"
                  )}
                  title={preset.desc}
                >
                  {preset.label}
                </Button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Compact Preview Info */}
      <div className="p-3 bg-gradient-to-r from-purple/10 to-cyan/10 border border-purple-muted/30 rounded-lg">
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center space-x-2">
            <Camera className="w-4 h-4 text-white" />
            <span className="text-white font-medium">Preview:</span>
          </div>
          <div className="flex items-center space-x-4 text-xs">
            <span className="text-grey-light/70">
              {Math.round(3600 / form.captureInterval)}/hour
            </span>
            <span className="text-grey-light/70">
              {Math.round(86400 / form.captureInterval).toLocaleString()}/day
            </span>
            <span className="text-grey-light/70">
              ~{Math.round((86400 / form.captureInterval) * 0.5)} MB/day
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}