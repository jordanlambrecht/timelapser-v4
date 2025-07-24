import { FolderOpen, Trash2, Star, Download, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"

interface BulkActionsDrawerProps {
  show: boolean
  selectedIds: number[]
  selectedCount: number
  onClearSelection: () => void
  onBulkAction: (action: string) => void
}

export function BulkActionsDrawer({
  show,
  selectedIds,
  selectedCount,
  onClearSelection,
  onBulkAction,
}: BulkActionsDrawerProps) {
  if (!show) return null

  const handleAction = (action: string) => {
    onBulkAction(action)
  }

  return (
    <div className="fixed inset-x-0 bottom-0 z-50">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/20" onClick={onClearSelection} />
      
      {/* Drawer */}
      <div className="relative bg-gray-900 text-white border-t border-gray-700 shadow-lg">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Left Side - Selection Info */}
            <div className="flex items-center space-x-4">
              <Badge 
                variant="secondary" 
                className="bg-blue-600 text-white border-blue-500"
              >
                {selectedCount} selected
              </Badge>
              <span className="text-sm text-gray-300">
                {selectedCount === 1 
                  ? "1 timelapse selected" 
                  : `${selectedCount} timelapses selected`
                }
              </span>
            </div>

            {/* Center - Actions */}
            <div className="flex items-center space-x-2">
              {/* Move to Folder - Future Feature */}
              <Button
                variant="ghost"
                size="sm"
                disabled
                className="text-white hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => handleAction("move")}
                title="Coming soon"
              >
                <FolderOpen className="h-4 w-4 mr-2" />
                Move
              </Button>

              {/* Delete */}
              <Button
                variant="ghost"
                size="sm"
                className="text-white hover:bg-red-800 hover:text-red-100"
                onClick={() => handleAction("delete")}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete
              </Button>

              {/* Star */}
              <Button
                variant="ghost"
                size="sm"
                className="text-white hover:bg-gray-800"
                onClick={() => handleAction("star")}
              >
                <Star className="h-4 w-4 mr-2" />
                Star
              </Button>

              {/* Download */}
              <Button
                variant="ghost"
                size="sm"
                className="text-white hover:bg-gray-800"
                onClick={() => handleAction("download")}
              >
                <Download className="h-4 w-4 mr-2" />
                Download
              </Button>
            </div>

            {/* Right Side - Close */}
            <Button
              variant="ghost"
              size="sm"
              className="text-white hover:bg-gray-800"
              onClick={onClearSelection}
            >
              <X className="h-4 w-4 mr-2" />
              Clear
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
