import { useState } from "react"
import { Star, MoreVertical, Calendar, Camera, ImageIcon, Video, Play } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { ContextMenu } from "./context-menu"
import { formatRelativeTime } from "@/lib/time-utils"
import type { TimelapseForLibrary } from "@/hooks/use-timelapse-library"

interface TimelapseCardProps {
  timelapse: TimelapseForLibrary
  isSelected: boolean
  onSelect: () => void
  onDeselect: () => void
  onStarToggle: (id: number, starred: boolean) => void
  onAction: (action: string, timelapse: TimelapseForLibrary) => void
}

export function TimelapseCard({
  timelapse,
  isSelected,
  onSelect,
  onDeselect,
  onStarToggle,
  onAction,
}: TimelapseCardProps) {
  const [isHovered, setIsHovered] = useState(false)
  const [showContextMenu, setShowContextMenu] = useState(false)

  const handleStarClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    onStarToggle(timelapse.id, !timelapse.starred)
  }

  const handleCheckboxChange = (checked: boolean) => {
    if (checked) {
      onSelect()
    } else {
      onDeselect()
    }
  }

  const handleCardClick = () => {
    // Navigate to individual timelapse page
    window.location.href = `/timelapses/${timelapse.id}`
  }

  const getStatusBadge = () => {
    if (timelapse.is_active) {
      return (
        <Badge className="bg-success/20 text-success border border-success/40 rounded-full px-2 py-1">
          🟢 Active
        </Badge>
      )
    }
    
    const statusConfig = {
      completed: "bg-cyan/20 text-cyan border-cyan/40",
      stopped: "bg-purple/20 text-purple-light border-purple/40", 
      archived: "bg-grey-light/20 text-grey-light border-grey-light/40"
    } as const

    const color = statusConfig[timelapse.status as keyof typeof statusConfig] || statusConfig.completed

    return (
      <Badge className={`${color} rounded-full px-2 py-1 border`}>
        {timelapse.status.charAt(0).toUpperCase() + timelapse.status.slice(1)}
      </Badge>
    )
  }

  return (
    <div
      className={`relative group cursor-pointer transition-all duration-300 hover-lift ${
        timelapse.is_active ? "ring-3 ring-success/60" : ""
      } ${isSelected ? "ring-2 ring-cyan/60" : ""}`}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={handleCardClick}
    >
      <div className={`glass rounded-2xl overflow-hidden border border-purple-muted/30 ${
        isSelected ? "bg-cyan/5 border-cyan/40" : ""
      } ${timelapse.is_active ? "border-success/60" : ""}`}>
        {/* Checkbox - shown on hover or when selected */}
        {(isHovered || isSelected) && (
          <div className="absolute top-3 left-3 z-10">
            <div className="p-1 bg-black/60 rounded-lg backdrop-blur-sm">
              <Checkbox
                checked={isSelected}
                onCheckedChange={handleCheckboxChange}
                className="border-white/60 data-[state=checked]:bg-cyan data-[state=checked]:border-cyan"
                onClick={(e) => e.stopPropagation()}
              />
            </div>
          </div>
        )}

        {/* Star - always visible if starred, visible on hover if not */}
        <Button
          variant="ghost"
          size="sm"
          className={`absolute top-3 right-12 z-10 h-8 w-8 p-0 bg-black/60 backdrop-blur-sm rounded-lg ${
            timelapse.starred || isHovered ? "opacity-100" : "opacity-0"
          } transition-all duration-300 hover:bg-black/80`}
          onClick={handleStarClick}
        >
          <Star
            className={`h-4 w-4 ${
              timelapse.starred ? "fill-yellow text-yellow" : "text-white"
            }`}
          />
        </Button>

        {/* Context Menu Button */}
        <Button
          variant="ghost"
          size="sm"
          className={`absolute top-3 right-3 z-10 h-8 w-8 p-0 bg-black/60 backdrop-blur-sm rounded-lg ${
            isHovered ? "opacity-100" : "opacity-0"
          } transition-all duration-300 hover:bg-black/80`}
          onClick={(e) => {
            e.stopPropagation()
            setShowContextMenu(true)
          }}
        >
          <MoreVertical className="h-4 w-4 text-white" />
        </Button>

        {/* Thumbnail Area */}
        <div className="relative aspect-video bg-black/40 overflow-hidden">
          {timelapse.latest_image_path ? (
            <img
              src={timelapse.latest_image_path}
              alt={`${timelapse.name || `Timelapse ${timelapse.id}`} preview`}
              className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-grey-light/40">
              <ImageIcon className="h-12 w-12" />
            </div>
          )}

          {/* Active Badge Overlay */}
          {timelapse.is_active && (
            <div className="absolute bottom-3 left-3">
              <Badge className="bg-success/90 text-white border-success rounded-full px-2 py-1 text-xs backdrop-blur-sm">
                🟢 Live
              </Badge>
            </div>
          )}

          {/* Video Count Overlay */}
          {timelapse.video_count > 0 && (
            <div className="absolute bottom-3 right-3">
              <Badge className="bg-black/60 text-white border-purple-muted/40 rounded-full px-2 py-1 text-xs backdrop-blur-sm flex items-center space-x-1">
                <Video className="h-3 w-3" />
                <span>{timelapse.video_count}</span>
              </Badge>
            </div>
          )}
        </div>

        {/* Content */}
        <div className="p-4 space-y-3">
          {/* Title */}
          <div>
            <h3 className="font-semibold text-white line-clamp-1 text-lg">
              {timelapse.name || `Timelapse #${timelapse.id}`}
            </h3>
          </div>

          {/* Camera & Status */}
          <div className="flex items-center space-x-2 text-sm text-grey-light/70">
            <Camera className="h-4 w-4 text-cyan" />
            <span className="line-clamp-1">{timelapse.camera_name}</span>
          </div>

          {/* Date & Image Count */}
          <div className="flex items-center justify-between text-sm text-grey-light/60">
            <div className="flex items-center space-x-2">
              <Calendar className="h-4 w-4" />
              <span>{formatRelativeTime(timelapse.created_at)}</span>
            </div>
            <div className="flex items-center space-x-2">
              <ImageIcon className="h-4 w-4" />
              <span className="font-medium text-white">{timelapse.image_count.toLocaleString()}</span>
            </div>
          </div>

          {/* Status Badge */}
          <div className="flex justify-start">
            {getStatusBadge()}
          </div>
        </div>
      </div>

      {/* Context Menu */}
      <ContextMenu
        isOpen={showContextMenu}
        onClose={() => setShowContextMenu(false)}
        timelapse={timelapse}
        onAction={onAction}
      />
    </div>
  )
}
