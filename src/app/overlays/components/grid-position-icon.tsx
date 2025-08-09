// src/app/overlays/components/grid-position-icon.tsx
"use client"

import { cn } from "@/lib/utils"
import type { OverlayItem } from "@/hooks/use-overlay-presets"

interface GridPositionIconProps {
  positions: string[]
  className?: string
}

/**
 * Helper function to extract positions from overlay items
 */
export function getOverlayPositions(overlayItems: OverlayItem[]): string[] {
  return overlayItems.map((item) => item.position)
}

export function GridPositionIcon({
  positions,
  className,
}: GridPositionIconProps) {
  return (
    <div className={cn("grid grid-cols-3 gap-1 w-fit", className)}>
      {[
        "topLeft",
        "topCenter",
        "topRight",
        "centerLeft",
        "center",
        "centerRight",
        "bottomLeft",
        "bottomCenter",
        "bottomRight",
      ].map((position) => (
        <div
          key={position}
          className={cn(
            "w-6 h-4 rounded-sm border transition-colors duration-150",
            positions.includes(position)
              ? "bg-purple/30 border-purple/50"
              : "bg-purple-muted/10 border-purple-muted/20"
          )}
        />
      ))}
    </div>
  )
}
