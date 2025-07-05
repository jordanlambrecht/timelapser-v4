// src/components/ui/interval-quick-presets.tsx
"use client"

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"

interface IntervalQuickPresetsProps {
  value: number
  onChange: (value: number) => void
  disabled?: boolean
  className?: string
  title?: string
}

const presets = [
  { label: "30s", value: 30, desc: "High detail" },
  { label: "1m", value: 60, desc: "Detailed" },
  { label: "5m", value: 300, desc: "Standard" },
  { label: "15m", value: 900, desc: "Moderate" },
  { label: "1h", value: 3600, desc: "Long-term" },
  { label: "2h", value: 7200, desc: "Longer-term" },
]

export const formatInterval = (seconds: number) => {
  const sec = seconds
  if (sec < 60) return `${sec} seconds`
  if (sec < 3600) return `${Math.floor(sec / 60)} minutes`
  return `${Math.floor(sec / 3600)} hours`
}

export function IntervalQuickPresets({
  value,
  onChange,
  disabled = false,
  className,
  title = "Quick Presets:",
}: IntervalQuickPresetsProps) {
  return (
    <div className={cn("space-y-4", className)}>
      <Label className="text-xs text-muted-foreground">
        {title}
      </Label>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-2 gap-2">
        {presets.map((preset) => (
          <Button
            key={preset.value}
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onChange(preset.value)}
            className={cn(
              "text-xs h-8 px-2 border-borderColor/50 hover:border-primary/50 transition-all duration-300 ease-in-out",
              value === preset.value
                ? "bg-primary border-primary/50 text-blue"
                : "bg-background/30 text-muted-foreground hover:text-foreground"
            )}
            disabled={disabled}
            title={preset.desc}
          >
            {preset.label}
          </Button>
        ))}
      </div>
    </div>
  )
}