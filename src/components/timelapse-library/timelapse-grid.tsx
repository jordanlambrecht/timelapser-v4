import { useMemo } from "react"
import { Camera, Calendar, ImageIcon, Video, Star, MoreVertical } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { TimelapseCard } from "./timelapse-card"
import { ContextMenu } from "./context-menu"
import { formatRelativeTime } from "@/lib/time-utils"
import type { ViewMode, SortBy } from "@/app/timelapses/page"
import type { TimelapseForLibrary } from "@/hooks/use-timelapse-library"

interface TimelapseGridProps {
  timelapses: TimelapseForLibrary[]
  viewMode: ViewMode
  sortBy: SortBy
  selectedIds: number[]
  onSelect: (id: number) => void
  onDeselect: (id: number) => void
  isSelected: (id: number) => boolean
}

export function TimelapseGrid({
  timelapses,
  viewMode,
  sortBy,
  selectedIds,
  onSelect,
  onDeselect,
  isSelected,
}: TimelapseGridProps) {
  // Group timelapses by camera when sorted by camera
  const groupedTimelapses = useMemo(() => {
    if (sortBy === "camera") {
      const groups = timelapses.reduce((acc, timelapse) => {
        const cameraName = timelapse.camera_name || "Unknown Camera"
        if (!acc[cameraName]) {
          acc[cameraName] = []
        }
        acc[cameraName].push(timelapse)
        return acc
      }, {} as Record<string, TimelapseForLibrary[]>)

      return Object.entries(groups).map(([cameraName, timelapses]) => ({
        cameraName,
        timelapses,
      }))
    }

    return [{ cameraName: null, timelapses }]
  }, [timelapses, sortBy])

  const handleStarToggle = async (id: number, starred: boolean) => {
    // TODO: Implement API call to update starred status
    console.log(`Toggle star for timelapse ${id}: ${starred}`)
  }

  const handleAction = async (action: string, timelapse: TimelapseForLibrary) => {
    // TODO: Implement actions
    console.log(`Action: ${action} on timelapse ${timelapse.id}`)
    
    switch (action) {
      case "view_details":
        window.location.href = `/timelapses/${timelapse.id}`
        break
      case "rename":
        // TODO: Open rename modal
        break
      case "download_images":
        // TODO: Start download
        break
      case "toggle_star":
        handleStarToggle(timelapse.id, !timelapse.starred)
        break
      case "delete":
        // TODO: Show confirmation and delete
        break
      default:
        console.log(`Unhandled action: ${action}`)
    }
  }

  if (timelapses.length === 0) {
    return (
      <Card className="p-12 text-center">
        <div className="space-y-4">
          <div className="text-gray-400">
            <Video className="h-12 w-12 mx-auto" />
          </div>
          <div>
            <h3 className="text-lg font-medium text-gray-900">No timelapses found</h3>
            <p className="text-gray-600">Start creating timelapses from your cameras to see them here.</p>
          </div>
        </div>
      </Card>
    )
  }

  if (viewMode === "row") {
    return (
      <div className="space-y-6">
        {groupedTimelapses.map((group) => (
          <div key={group.cameraName || "all"}>
            {/* Camera Section Header */}
            {group.cameraName && (
              <div className="flex items-center space-x-2 mb-4">
                <Camera className="h-5 w-5 text-gray-600" />
                <h3 className="text-lg font-semibold text-gray-900">
                  {group.cameraName}
                </h3>
                <Badge variant="secondary" className="text-xs">
                  {group.timelapses.length} timelapses
                </Badge>
              </div>
            )}

            {/* Table View */}
            <Card>
              <div className="overflow-hidden">
                {/* Table Header */}
                <div className="grid grid-cols-12 gap-4 p-4 border-b border-gray-100 bg-gray-50 text-sm font-medium text-gray-600">
                  <div className="col-span-1 flex items-center">
                    <Checkbox
                      checked={group.timelapses.every(t => isSelected(t.id))}
                      onCheckedChange={(checked) => {
                        if (checked) {
                          group.timelapses.forEach(t => onSelect(t.id))
                        } else {
                          group.timelapses.forEach(t => onDeselect(t.id))
                        }
                      }}
                    />
                  </div>
                  <div className="col-span-1">Preview</div>
                  <div className="col-span-3">Title</div>
                  <div className="col-span-2">Camera</div>
                  <div className="col-span-1">Images</div>
                  <div className="col-span-1">Videos</div>
                  <div className="col-span-2">Added</div>
                  <div className="col-span-1">Actions</div>
                </div>

                {/* Table Rows */}
                <div className="divide-y divide-gray-100">
                  {group.timelapses.map((timelapse) => (
                    <TimelapseRow
                      key={timelapse.id}
                      timelapse={timelapse}
                      isSelected={isSelected(timelapse.id)}
                      onSelect={() => onSelect(timelapse.id)}
                      onDeselect={() => onDeselect(timelapse.id)}
                      onStarToggle={handleStarToggle}
                      onAction={handleAction}
                    />
                  ))}
                </div>
              </div>
            </Card>
          </div>
        ))}
      </div>
    )
  }

  // Card View
  return (
    <div className="space-y-6">
      {groupedTimelapses.map((group) => (
        <div key={group.cameraName || "all"}>
          {/* Camera Section Header */}
          {group.cameraName && (
            <div className="flex items-center space-x-2 mb-4">
              <Camera className="h-5 w-5 text-gray-600" />
              <h3 className="text-lg font-semibold text-gray-900">
                {group.cameraName}
              </h3>
              <Badge variant="secondary" className="text-xs">
                {group.timelapses.length} timelapses
              </Badge>
            </div>
          )}

          {/* Card Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {group.timelapses.map((timelapse) => (
              <TimelapseCard
                key={timelapse.id}
                timelapse={timelapse}
                isSelected={isSelected(timelapse.id)}
                onSelect={() => onSelect(timelapse.id)}
                onDeselect={() => onDeselect(timelapse.id)}
                onStarToggle={handleStarToggle}
                onAction={handleAction}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// Row component for table view
interface TimelapseRowProps {
  timelapse: TimelapseForLibrary
  isSelected: boolean
  onSelect: () => void
  onDeselect: () => void
  onStarToggle: (id: number, starred: boolean) => void
  onAction: (action: string, timelapse: TimelapseForLibrary) => void
}

function TimelapseRow({
  timelapse,
  isSelected,
  onSelect,
  onDeselect,
  onStarToggle,
  onAction,
}: TimelapseRowProps) {
  const handleRowClick = () => {
    window.location.href = `/timelapses/${timelapse.id}`
  }

  const getStatusBadge = () => {
    if (timelapse.is_active) {
      return (
        <Badge className="bg-green-100 text-green-800 border-green-200 text-xs">
          🟢 Active
        </Badge>
      )
    }
    
    const statusColors = {
      completed: "bg-blue-100 text-blue-800 border-blue-200",
      stopped: "bg-gray-100 text-gray-800 border-gray-200", 
      archived: "bg-gray-100 text-gray-600 border-gray-200"
    } as const

    const color = statusColors[timelapse.status as keyof typeof statusColors] || statusColors.completed

    return (
      <Badge className={`${color} text-xs`}>
        {timelapse.status.charAt(0).toUpperCase() + timelapse.status.slice(1)}
      </Badge>
    )
  }

  return (
    <div
      className={`grid grid-cols-12 gap-4 p-4 hover:bg-gray-50 cursor-pointer transition-colors ${
        isSelected ? "bg-blue-50" : ""
      } ${timelapse.is_active ? "ring-1 ring-green-200" : ""}`}
      onClick={handleRowClick}
    >
      {/* Checkbox */}
      <div className="col-span-1 flex items-center">
        <Checkbox
          checked={isSelected}
          onCheckedChange={(checked) => checked ? onSelect() : onDeselect()}
          onClick={(e) => e.stopPropagation()}
        />
      </div>

      {/* Thumbnail */}
      <div className="col-span-1 flex items-center">
        <div className="w-10 h-6 bg-gray-100 rounded overflow-hidden">
          {timelapse.latest_image_path ? (
            <img
              src={timelapse.latest_image_path}
              alt=""
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <ImageIcon className="h-3 w-3 text-gray-400" />
            </div>
          )}
        </div>
      </div>

      {/* Title */}
      <div className="col-span-3 flex items-center space-x-2">
        <span className="font-medium text-gray-900 line-clamp-1">
          {timelapse.name || `Timelapse #${timelapse.id}`}
        </span>
        {timelapse.starred && (
          <Star className="h-4 w-4 fill-yellow-400 text-yellow-400 flex-shrink-0" />
        )}
        {getStatusBadge()}
      </div>

      {/* Camera */}
      <div className="col-span-2 flex items-center text-sm text-gray-600">
        {timelapse.camera_name}
      </div>

      {/* Image Count */}
      <div className="col-span-1 flex items-center text-sm text-gray-600">
        {timelapse.image_count.toLocaleString()}
      </div>

      {/* Video Count */}
      <div className="col-span-1 flex items-center text-sm text-gray-600">
        {timelapse.video_count}
      </div>

      {/* Date Added */}
      <div className="col-span-2 flex items-center text-sm text-gray-600">
        {formatRelativeTime(timelapse.created_at)}
      </div>

      {/* Actions */}
      <div className="col-span-1 flex items-center">
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0"
          onClick={(e) => {
            e.stopPropagation()
            // TODO: Show context menu
            onAction("context_menu", timelapse)
          }}
        >
          <MoreVertical className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}
