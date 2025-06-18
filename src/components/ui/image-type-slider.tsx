// src/components/ui/image-type-slider.tsx
"use client"

import { useState } from "react"
import { cn } from "@/lib/utils"

interface ImageTypeSliderProps {
  value: "PNG" | "JPG"
  onValueChange: (value: "PNG" | "JPG") => void
  disabled?: boolean
  className?: string
}

// TODO: NEEDS BRAND COLORS
export function ImageTypeSlider({
  value,
  onValueChange,
  disabled = false,
  className,
}: ImageTypeSliderProps) {
  const [isAnimating, setIsAnimating] = useState(false)

  const handleToggle = () => {
    if (disabled) return

    setIsAnimating(true)
    const newValue = value === "PNG" ? "JPG" : "PNG"
    onValueChange(newValue)

    // Reset animation state
    setTimeout(() => setIsAnimating(false), 200)
  }

  return (
    <div className={cn("space-y-3", className)}>
      <div
        className={cn(
          "max-w-48 relative flex items-center w-full h-12 rounded-full p-1 transition-all duration-700 cursor-pointer ease-in-out",
          "bg-background/30 border border-borderColor/50 hover:border-borderColor/70",
          disabled && "opacity-50 cursor-not-allowed ",
          isAnimating && "scale-[0.98]"
        )}
        onClick={handleToggle}
      >
        {/* Background slider track */}
        <div className='absolute inset-1 rounded-full bg-muted/20' />

        {/* Moving indicator */}
        <div
          className={cn(
            "absolute top-1 h-10 w-1/2 rounded-full transition-all duration-700 ease-in-out",
            "bg-gradient-to-r shadow-lg border border-primary/20",
            value === "PNG"
              ? "left-1 from-cyan/69 to-cyan/69 bg-cyan/30"
              : "left-1/2 from-yellow/80 to-cyan/69 bg-yellow/80 text-blue"
          )}
        />

        {/* Labels */}
        <div className='relative z-10 flex w-full'>
          <div
            className={cn(
              "flex-1 flex items-center justify-center text-sm font-medium transition-all duration-700 ease-in-out",
              value === "PNG"
                ? "text-cyan drop-shadow-sm"
                : "text-muted-foreground"
            )}
          >
            PNG
          </div>
          <div
            className={cn(
              "flex-1 flex items-center justify-center text-sm font-medium transition-all duration-700 ease-in-out",
              value === "JPG"
                ? "text-blue drop-shadow-sm"
                : "text-muted-foreground"
            )}
          >
            JPG
          </div>
        </div>
      </div>

      {/* Information text */}
      <div className='p-3 rounded-lg bg-background/30 min-h-[60px]'>
        <div className='text-xs text-muted-foreground relative'>
          <div
            className={cn(
              "absolute top-0 left-0 right-0 transition-opacity duration-700 ease-in-out",
              value === "PNG" ? "opacity-100" : "opacity-0"
            )}
            aria-hidden={value !== "PNG"}
          >
            <strong className='text-blue-400'>PNG:</strong> Lossless quality,
            larger files, ideal for detailed analysis
          </div>
          <div
            className={cn(
              "absolute top-0 left-0 right-0 transition-opacity duration-700 ease-in-out",
              value === "JPG" ? "opacity-100" : "opacity-0"
            )}
            aria-hidden={value !== "JPG"}
          >
            <strong className='text-orange-400'>JPG:</strong> Better
            compression, smaller files, good for most timelapses
          </div>
        </div>
      </div>
    </div>
  )
}
