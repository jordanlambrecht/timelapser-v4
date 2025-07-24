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
import { GRID_POSITIONS, POSITION_LABELS, OVERLAY_TYPES, type GridPosition, type OverlayType } from "@/lib/overlay-presets-data"

interface OverlayItem {
  type: OverlayType
  customText?: string
  textSize: number
  textColor: string
  backgroundColor?: string
  backgroundOpacity: number
  dateFormat?: string
  imageUrl?: string
  imageScale: number
}

interface OverlayGridProps {
  overlayPositions: Partial<Record<GridPosition, OverlayItem>>
  selectedPosition: GridPosition | null
  onPositionSelect: (position: GridPosition | null) => void
  onAddOverlay: (position: GridPosition, type: OverlayType) => void
  onRemoveOverlay: (position: GridPosition) => void
  livePreview?: boolean
  globalOptions?: {
    opacity: number
    dropShadow: number
    font: string
    xMargin: number
    yMargin: number
  }
}

export function OverlayGrid({
  overlayPositions,
  selectedPosition,
  onPositionSelect,
  onAddOverlay,
  onRemoveOverlay,
  livePreview = false,
  globalOptions = { opacity: 100, dropShadow: 0, font: "Arial", xMargin: 20, yMargin: 20 },
}: OverlayGridProps) {
  const [openDropdown, setOpenDropdown] = useState<GridPosition | null>(null)
  
  const getOverlayTypeData = (type: OverlayType) => {
    return OVERLAY_TYPES.find(t => t.value === type)
  }

  if (livePreview) {
    // Live preview mode - show actual overlays positioned directly
    return (
      <div style={{ position: 'relative', width: '100%', height: '100%' }}>
        {GRID_POSITIONS.map((position) => {
          const overlay = overlayPositions[position]
          if (!overlay) return null

          const positionStyles = getPositionStyles(position, globalOptions)
          
          return (
            <div
              key={position}
              className="text-white pointer-events-none px-2 py-1 rounded whitespace-nowrap"
              style={{
                ...positionStyles,
                opacity: globalOptions.opacity / 100,
                fontFamily: globalOptions.font,
                fontSize: `${overlay.textSize}px`,
                color: overlay.textColor,
                textShadow: globalOptions.dropShadow > 0 ? 
                  `${globalOptions.dropShadow}px ${globalOptions.dropShadow}px ${globalOptions.dropShadow * 2}px rgba(0, 0, 0, 0.8)` : 
                  'none',
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
      className="absolute grid grid-cols-3 gap-6"
      style={{
        top: `${globalOptions.yMargin + 8}px`,
        left: `${globalOptions.xMargin + 8}px`,
        right: `${globalOptions.xMargin + 8}px`,
        bottom: `${globalOptions.yMargin + 8}px`,
      }}
    >
        {GRID_POSITIONS.map((position) => {
          const overlay = overlayPositions[position]
          const isSelected = selectedPosition === position
          
          if (overlay) {
            // Cell with overlay content
            return (
              <div
                key={position}
                onClick={() => onPositionSelect(position)}
                className={cn(
                  "relative border-2 rounded-lg p-3 cursor-pointer transition-all duration-200 flex flex-col justify-between",
                  isSelected 
                    ? "border-cyan/70 bg-cyan/20 backdrop-blur-sm" 
                    : "border-purple/50 bg-purple/20 backdrop-blur-sm hover:border-purple hover:bg-purple/30"
                )}
              >
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <Badge 
                      variant="secondary" 
                      className="text-xs bg-purple-light/20 text-purple-light border-purple-light/30"
                    >
                      {getOverlayTypeData(overlay.type)?.label}
                    </Badge>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation()
                        onRemoveOverlay(position)
                      }}
                      className="h-4 w-4 p-0 hover:bg-failure/20 hover:text-failure"
                    >
                      <X className="w-3 h-3" />
                    </Button>
                  </div>
                  <p className="text-xs text-grey-light/60 font-medium">
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
                  <Plus className="w-6 h-6 text-grey-light/60 mb-2" />
                  <p className="text-xs text-grey-light/60 font-medium text-center">
                    {POSITION_LABELS[position]}
                  </p>
                </div>
              </DropdownMenuTrigger>
              <DropdownMenuContent 
                className="w-56 bg-black/95 backdrop-blur-xl border-purple/30"
                align="center"
                sideOffset={5}
              >
                <DropdownMenuLabel className="text-cyan">
                  Add overlay to {POSITION_LABELS[position]}
                </DropdownMenuLabel>
                <DropdownMenuSeparator className="bg-purple-muted/30" />
                {OVERLAY_TYPES.map((type) => (
                  <DropdownMenuItem
                    key={type.value}
                    onClick={() => {
                      onAddOverlay(position, type.value)
                      setOpenDropdown(null)
                    }}
                    className="cursor-pointer hover:bg-purple/20 hover:text-white"
                  >
                    <div className="flex flex-col">
                      <span className="font-medium">{type.label}</span>
                      <span className="text-xs text-grey-light/60">{type.description}</span>
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
  function getPositionStyles(position: GridPosition, globalOptions: any) {
    const margin = { x: globalOptions.xMargin, y: globalOptions.yMargin }
    
    switch (position) {
      case 'topLeft':
        return { 
          position: 'absolute',
          top: `${margin.y}px`, 
          left: `${margin.x}px`,
          right: 'auto',
          bottom: 'auto'
        }
      case 'topCenter':
        return { 
          position: 'absolute',
          top: `${margin.y}px`, 
          left: '50%', 
          right: 'auto',
          bottom: 'auto',
          transform: 'translateX(-50%)' 
        }
      case 'topRight':
        return { 
          position: 'absolute',
          top: `${margin.y}px`, 
          right: `${margin.x}px`,
          left: 'auto',
          bottom: 'auto'
        }
      case 'centerLeft':
        return { 
          position: 'absolute',
          top: '50%', 
          left: `${margin.x}px`,
          right: 'auto', 
          bottom: 'auto',
          transform: 'translateY(-50%)' 
        }
      case 'center':
        return { 
          position: 'absolute',
          top: '50%', 
          left: '50%',
          right: 'auto',
          bottom: 'auto', 
          transform: 'translate(-50%, -50%)' 
        }
      case 'centerRight':
        return { 
          position: 'absolute',
          top: '50%', 
          right: `${margin.x}px`,
          left: 'auto',
          bottom: 'auto', 
          transform: 'translateY(-50%)' 
        }
      case 'bottomLeft':
        return { 
          position: 'absolute',
          bottom: `${margin.y}px`, 
          left: `${margin.x}px`,
          top: 'auto',
          right: 'auto'
        }
      case 'bottomCenter':
        return { 
          position: 'absolute',
          bottom: `${margin.y}px`, 
          left: '50%',
          top: 'auto',
          right: 'auto', 
          transform: 'translateX(-50%)' 
        }
      case 'bottomRight':
        return { 
          position: 'absolute',
          bottom: `${margin.y}px`, 
          right: `${margin.x}px`,
          top: 'auto',
          left: 'auto'
        }
      default:
        return { 
          position: 'absolute',
          top: '0px', 
          left: '0px',
          right: 'auto',
          bottom: 'auto'
        }
    }
  }

  function getOverlayContent(overlay: OverlayItem) {
    switch (overlay.type) {
      case 'custom_text':
        return overlay.customText || 'Custom Text'
      case 'timestamp':
        return new Date().toLocaleString()
      case 'date_only':
        return new Date().toLocaleDateString()
      case 'time_only':
        return new Date().toLocaleTimeString()
      case 'camera_name':
        return 'Camera Name'
      case 'weather_current':
        return '72°F Sunny'
      case 'watermark':
      case 'image':
        if (overlay.imageUrl) {
          return (
            <img 
              src={overlay.imageUrl} 
              alt="Overlay" 
              style={{ 
                width: 'auto',
                height: 'auto',
                maxWidth: '100px',
                maxHeight: '50px',
                transform: `scale(${(overlay.imageScale || 100) / 100})`,
                objectFit: 'contain'
              }}
            />
          )
        }
        return 'Upload Image'
      default:
        return 'Overlay'
    }
  }
}