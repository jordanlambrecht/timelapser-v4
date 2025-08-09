// src/app/overlays/components/overlay-grid.tsx
"use client"

import { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Plus, X } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  GRID_POSITIONS,
  POSITION_LABELS,
  OVERLAY_TYPES,
  type GridPosition,
  type OverlayType,
} from "@/lib/overlay-presets-data"
import type { OverlayItem, GlobalSettings } from "@/hooks/use-overlay-presets"

interface OverlayGridProps {
  overlayItems: OverlayItem[]
  selectedItemId: string | null
  onItemSelect: (itemId: string | null) => void
  onAddOverlay: (position: GridPosition, type: OverlayType) => void
  onRemoveOverlay: (itemId: string) => void
  livePreview?: boolean
  globalSettings?: GlobalSettings
}

export function OverlayGrid({
  overlayItems,
  selectedItemId,
  onItemSelect,
  onAddOverlay,
  onRemoveOverlay,
  livePreview = false,
  globalSettings = {
    opacity: 100,
    dropShadow: 0,
    font: "Arial",
    xMargin: 20,
    yMargin: 20,
    backgroundColor: "rgba(0,0,0,0.5)",
    backgroundOpacity: 50,
    fillColor: "#ffffff",
  },
}: OverlayGridProps) {
  const [openDropdown, setOpenDropdown] = useState<GridPosition | null>(null)

  const getOverlayTypeData = (type: OverlayType) => {
    return OVERLAY_TYPES.find((t) => t.value === type)
  }

  // Helper to find overlay item at a specific position
  const getOverlayAtPosition = (
    position: GridPosition
  ): OverlayItem | undefined => {
    return overlayItems.find((item) => item.position === position)
  }

  if (livePreview) {
    // Live preview mode - show actual overlays positioned directly
    return (
      <div style={{ position: "relative", width: "100%", height: "100%" }}>
        {GRID_POSITIONS.map((position) => {
          const overlay = getOverlayAtPosition(position)
          if (!overlay || !overlay.enabled) return null

          const positionStyles = getPositionStyles(position, globalSettings)
          const settings = overlay.settings || {}

          return (
            <div
              key={position}
              className='text-white pointer-events-none px-2 py-1 rounded whitespace-nowrap'
              style={{
                ...positionStyles,
                opacity: globalSettings.opacity / 100,
                fontFamily: globalSettings.font,
                fontSize: `${settings.textSize || 16}px`,
                color: settings.textColor || "#ffffff",
                textShadow:
                  globalSettings.dropShadow > 0
                    ? `${globalSettings.dropShadow}px ${
                        globalSettings.dropShadow
                      }px ${globalSettings.dropShadow * 2}px rgba(0, 0, 0, 0.8)`
                    : "none",
                zIndex: 25,
              }}
            >
              {getOverlayContent(overlay)}
            </div>
          )
        })}
      </div>
    )
  }

  // Grid mode - show positioning grid
  return (
    <div
      className='absolute grid grid-cols-3 gap-6'
      style={{
        top: `${globalSettings.yMargin + 8}px`,
        left: `${globalSettings.xMargin + 8}px`,
        right: `${globalSettings.xMargin + 8}px`,
        bottom: `${globalSettings.yMargin + 8}px`,
      }}
    >
      {GRID_POSITIONS.map((position) => {
        const overlay = getOverlayAtPosition(position)
        const isSelected = selectedItemId === overlay?.id

        if (overlay) {
          // Cell with overlay content
          return (
            <div
              key={position}
              onClick={() => onItemSelect(overlay.id)}
              className={cn(
                "relative border-2 rounded-lg p-3 cursor-pointer transition-all duration-200 flex flex-col justify-between",
                isSelected
                  ? "border-cyan/70 bg-cyan/20 backdrop-blur-sm"
                  : "border-purple/50 bg-purple/20 backdrop-blur-sm hover:border-purple hover:bg-purple/30"
              )}
            >
              <div className='space-y-1'>
                <div className='flex items-center justify-between'>
                  <Badge
                    variant='secondary'
                    className='text-xs bg-purple-light/20 text-purple-light border-purple-light/30'
                  >
                    {getOverlayTypeData(overlay.type)?.label}
                  </Badge>
                  <Button
                    size='sm'
                    variant='ghost'
                    onClick={(e) => {
                      e.stopPropagation()
                      onRemoveOverlay(overlay.id)
                    }}
                    className='h-4 w-4 p-0 hover:bg-failure/20 hover:text-failure'
                  >
                    <X className='w-3 h-3' />
                  </Button>
                </div>
                <p className='text-xs text-grey-light/60 font-medium'>
                  {POSITION_LABELS[position]}
                </p>
              </div>
            </div>
          )
        }

        // Empty cell with dropdown
        return (
          <DropdownMenu
            key={position}
            open={openDropdown === position}
            onOpenChange={(open) => setOpenDropdown(open ? position : null)}
          >
            <DropdownMenuTrigger asChild>
              <div
                className={cn(
                  "relative border-2 rounded-lg p-3 cursor-pointer transition-all duration-200 flex flex-col justify-center items-center",
                  openDropdown === position
                    ? "border-cyan/50 bg-cyan/10 backdrop-blur-sm"
                    : "border-purple-muted/30 bg-purple-muted/10 backdrop-blur-sm hover:border-purple-muted/50 hover:bg-purple-muted/20"
                )}
              >
                <Plus className='w-6 h-6 text-grey-light/60 mb-2' />
                <p className='text-xs text-grey-light/60 font-medium text-center'>
                  {POSITION_LABELS[position]}
                </p>
              </div>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              className='w-56 bg-black/95 backdrop-blur-xl border-purple/30'
              align='center'
              sideOffset={5}
            >
              <DropdownMenuLabel className='text-cyan'>
                Add overlay to {POSITION_LABELS[position]}
              </DropdownMenuLabel>
              <DropdownMenuSeparator className='bg-purple-muted/30' />
              {OVERLAY_TYPES.map((type) => (
                <DropdownMenuItem
                  key={type.value}
                  onClick={() => {
                    onAddOverlay(position, type.value)
                    setOpenDropdown(null)
                  }}
                  className='cursor-pointer hover:bg-purple/20 hover:text-white'
                >
                  <div className='flex flex-col'>
                    <span className='font-medium'>{type.label}</span>
                    <span className='text-xs text-grey-light/60'>
                      {type.description}
                    </span>
                  </div>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        )
      })}
    </div>
  )

  // Helper functions
  function getPositionStyles(
    position: GridPosition,
    globalSettings: GlobalSettings
  ): React.CSSProperties {
    const margin = { x: globalSettings.xMargin, y: globalSettings.yMargin }

    switch (position) {
      case "topLeft":
        return {
          position: "absolute",
          top: `${margin.y}px`,
          left: `${margin.x}px`,
          right: "auto",
          bottom: "auto",
        }
      case "topCenter":
        return {
          position: "absolute",
          top: `${margin.y}px`,
          left: "50%",
          right: "auto",
          bottom: "auto",
          transform: "translateX(-50%)",
        }
      case "topRight":
        return {
          position: "absolute",
          top: `${margin.y}px`,
          right: `${margin.x}px`,
          left: "auto",
          bottom: "auto",
        }
      case "centerLeft":
        return {
          position: "absolute",
          top: "50%",
          left: `${margin.x}px`,
          right: "auto",
          bottom: "auto",
          transform: "translateY(-50%)",
        }
      case "center":
        return {
          position: "absolute",
          top: "50%",
          left: "50%",
          right: "auto",
          bottom: "auto",
          transform: "translate(-50%, -50%)",
        }
      case "centerRight":
        return {
          position: "absolute",
          top: "50%",
          right: `${margin.x}px`,
          left: "auto",
          bottom: "auto",
          transform: "translateY(-50%)",
        }
      case "bottomLeft":
        return {
          position: "absolute",
          bottom: `${margin.y}px`,
          left: `${margin.x}px`,
          top: "auto",
          right: "auto",
        }
      case "bottomCenter":
        return {
          position: "absolute",
          bottom: `${margin.y}px`,
          left: "50%",
          top: "auto",
          right: "auto",
          transform: "translateX(-50%)",
        }
      case "bottomRight":
        return {
          position: "absolute",
          bottom: `${margin.y}px`,
          right: `${margin.x}px`,
          top: "auto",
          left: "auto",
        }
      default:
        return {
          position: "absolute",
          top: "0px",
          left: "0px",
          right: "auto",
          bottom: "auto",
        }
    }
  }

  function getOverlayContent(overlay: OverlayItem) {
    const settings = overlay.settings || {}

    switch (overlay.type) {
      case "custom_text":
        return settings.customText || "Custom Text"
      case "date_time":
        return new Date().toLocaleString()
      case "timelapse_name":
        return "Timelapse Name"
      case "frame_number":
        return "Frame 1234"
      case "day_number":
        return "Day 45"
      case "temperature":
        return "72°F"
      case "weather_conditions":
        return "Sunny"
      case "weather":
        return "72°F Sunny"
      case "watermark":
        if (settings.imageUrl) {
          return (
            <img
              src={settings.imageUrl}
              alt='Overlay'
              style={{
                width: "auto",
                height: "auto",
                maxWidth: "100px",
                maxHeight: "50px",
                transform: `scale(${(settings.imageScale || 100) / 100})`,
                objectFit: "contain",
              }}
            />
          )
        }
        return "Upload Image"
      default:
        return "Overlay"
    }
  }
}
