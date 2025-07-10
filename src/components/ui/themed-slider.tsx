// src/components/ui/themed-slider.tsx
"use client"

import { cn } from "@/lib/utils"
import { Label } from "@/components/ui/label"

interface ThemedSliderProps {
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  label?: string
  showValue?: boolean
  unit?: string
  disabled?: boolean
  className?: string
}

export function ThemedSlider({
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  label,
  showValue = true,
  unit = "",
  disabled = false,
  className,
}: ThemedSliderProps) {
  const percentage = ((value - min) / (max - min)) * 100

  return (
    <div className={cn("space-y-2", className)}>
      {label && (
        <div className="flex items-center justify-between">
          <Label className="text-sm font-medium text-white">
            {label}
          </Label>
          {showValue && (
            <span className="text-sm text-grey-light">
              {value}{unit}
            </span>
          )}
        </div>
      )}
      
      <div className="relative">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          disabled={disabled}
          className={cn(
            "w-full h-2 rounded-lg appearance-none cursor-pointer transition-all duration-200",
            "bg-purple-muted/30 hover:bg-purple-muted/40",
            "focus:outline-none focus:ring-2 focus:ring-pink/50 focus:ring-offset-2 focus:ring-offset-blue",
            "[&::-webkit-slider-thumb]:appearance-none",
            "[&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4",
            "[&::-webkit-slider-thumb]:rounded-full",
            "[&::-webkit-slider-thumb]:bg-gradient-to-r [&::-webkit-slider-thumb]:from-pink [&::-webkit-slider-thumb]:to-cyan",
            "[&::-webkit-slider-thumb]:border-0",
            "[&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:shadow-black/25",
            "[&::-webkit-slider-thumb]:hover:scale-110",
            "[&::-webkit-slider-thumb]:transition-transform [&::-webkit-slider-thumb]:duration-150",
            "[&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:w-4",
            "[&::-moz-range-thumb]:rounded-full",
            "[&::-moz-range-thumb]:bg-gradient-to-r [&::-moz-range-thumb]:from-pink [&::-moz-range-thumb]:to-cyan",
            "[&::-moz-range-thumb]:border-0",
            "[&::-moz-range-thumb]:shadow-lg",
            disabled && "opacity-50 cursor-not-allowed"
          )}
          style={{
            background: `linear-gradient(to right, 
              rgb(var(--color-pink)) 0%, 
              rgb(var(--color-cyan)) ${percentage}%, 
              rgb(var(--color-purple-muted) / 0.3) ${percentage}%, 
              rgb(var(--color-purple-muted) / 0.3) 100%)`
          }}
        />
      </div>
    </div>
  )
}