// src/app/overlays/components/preset-list-item.tsx
"use client"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Edit, Trash2, Eye, Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"
import type { OverlayPreset } from "@/hooks/use-overlay-presets"

interface PresetListItemProps {
  preset: OverlayPreset
  onEdit: (id: number) => void
  onDelete: (id: number) => void
  onPreview: (id: number) => void
}

export function PresetListItem({ preset, onEdit, onDelete, onPreview }: PresetListItemProps) {
  // Extract positions from overlay config
  const positions = preset.overlay_config?.overlayPositions ? Object.keys(preset.overlay_config.overlayPositions) : []
  const overlayCount = positions.length

  return (
    <div className="p-4 rounded-lg bg-purple-muted/10 border border-purple-muted/30 hover:border-purple/30 transition-all duration-200 hover:bg-purple-muted/20">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-1">
            <h5 className="font-medium text-white">{preset.name}</h5>
            {preset.is_builtin && (
              <Badge
                variant="outline"
                className="text-xs text-cyan border-cyan/30 bg-cyan/10"
              >
                <Sparkles className="w-3 h-3 mr-1" />
                Built-in
              </Badge>
            )}
          </div>
          
          <p className="text-sm text-grey-light/70 mb-2">
            {preset.description}
          </p>
          
          <div className="flex items-center space-x-4 text-xs text-grey-light/60">
            <span>{overlayCount} overlay{overlayCount !== 1 ? 's' : ''}</span>
            <span>•</span>
            <span>
              {preset.updated_at 
                ? `Updated ${new Date(preset.updated_at).toLocaleDateString()}`
                : "Never updated"
              }
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-2 ml-4">
          <Button
            size="sm"
            variant="outline"
            onClick={() => onPreview(preset.id)}
            className="border-purple-muted/50 hover:border-cyan/50 hover:text-cyan hover:bg-cyan/10"
          >
            <Eye className="w-4 h-4" />
          </Button>
          
          <Button
            size="sm"
            variant="outline"
            onClick={() => onEdit(preset.id)}
            className="border-purple-muted/50 hover:border-purple/50 hover:text-purple-light hover:bg-purple/10"
          >
            <Edit className="w-4 h-4" />
          </Button>
          
          {!preset.is_builtin && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => onDelete(preset.id)}
              className="border-purple-muted/50 hover:border-failure/50 hover:text-failure hover:bg-failure/10"
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          )}
        </div>
      </div>

      {/* Overlay Positions Preview */}
      <div className="mt-3 pt-3 border-t border-purple-muted/20">
        <div className="flex items-center space-x-2 mb-2">
          <span className="text-xs text-grey-light/60">Active positions:</span>
        </div>
        <div className="grid grid-cols-3 gap-1 w-fit">
          {["topLeft", "topCenter", "topRight", "centerLeft", "center", "centerRight", "bottomLeft", "bottomCenter", "bottomRight"].map((position) => (
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
      </div>
    </div>
  )
}