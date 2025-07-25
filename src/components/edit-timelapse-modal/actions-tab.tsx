// src/components/edit-timelapse-modal/actions-tab.tsx
"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import {
  Video,
  Trash2,
  RefreshCw,
  Image,
  Layers,
  Play,
  AlertTriangle,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "@/lib/toast"

interface ActionsTabProps {
  timelapse: {
    id: number
    name: string
    status: string
    image_count: number
    start_date: string
    last_capture_at?: string
  }
  cameraId: number
  cameraName: string
  onDataChange?: () => void
}

export function ActionsTab({
  timelapse,
  cameraId,
  cameraName,
  onDataChange,
}: ActionsTabProps) {
  const [loadingStates, setLoadingStates] = useState<Record<string, boolean>>({})

  const setLoading = (action: string, loading: boolean) => {
    setLoadingStates(prev => ({ ...prev, [action]: loading }))
  }

  const handleGenerateVideo = async () => {
    setLoading("generateVideo", true)
    try {
      const response = await fetch(`/api/timelapses/${timelapse.id}/generate-video`, {
        method: "POST",
      })

      if (!response.ok) {
        throw new Error("Failed to generate video")
      }

      toast.success("Video generation started! This may take a few minutes.")
      onDataChange?.()
    } catch (error) {
      console.error("Failed to generate video:", error)
      toast.error("Failed to start video generation")
    } finally {
      setLoading("generateVideo", false)
    }
  }

  const handleDeleteAllVideos = async () => {
    setLoading("deleteAllVideos", true)
    try {
      const response = await fetch(`/api/timelapses/${timelapse.id}/videos`, {
        method: "DELETE",
      })

      if (!response.ok) {
        throw new Error("Failed to delete videos")
      }

      toast.success("All videos deleted successfully")
      onDataChange?.()
    } catch (error) {
      console.error("Failed to delete videos:", error)
      toast.error("Failed to delete videos")
    } finally {
      setLoading("deleteAllVideos", false)
    }
  }

  const handleDeleteTimelapse = async () => {
    setLoading("deleteTimelapse", true)
    try {
      const response = await fetch(`/api/timelapses/${timelapse.id}`, {
        method: "DELETE",
      })

      if (!response.ok) {
        throw new Error("Failed to delete timelapse")
      }

      toast.success("Timelapse deleted successfully")
      // Note: This will likely close the modal and redirect
      onDataChange?.()
    } catch (error) {
      console.error("Failed to delete timelapse:", error)
      toast.error("Failed to delete timelapse")
    } finally {
      setLoading("deleteTimelapse", false)
    }
  }

  const handleReprocessOverlays = async () => {
    setLoading("reprocessOverlays", true)
    try {
      const response = await fetch(`/api/timelapses/${timelapse.id}/overlays/reprocess`, {
        method: "POST",
      })

      if (!response.ok) {
        throw new Error("Failed to reprocess overlays")
      }

      toast.success("Overlay reprocessing started")
      onDataChange?.()
    } catch (error) {
      console.error("Failed to reprocess overlays:", error)
      toast.error("Failed to start overlay reprocessing")
    } finally {
      setLoading("reprocessOverlays", false)
    }
  }

  const handleDeleteThumbnails = async () => {
    setLoading("deleteThumbnails", true)
    try {
      const response = await fetch(`/api/timelapses/${timelapse.id}/thumbnails`, {
        method: "DELETE",
      })

      if (!response.ok) {
        throw new Error("Failed to delete thumbnails")
      }

      toast.success("Thumbnails deleted successfully")
      onDataChange?.()
    } catch (error) {
      console.error("Failed to delete thumbnails:", error)
      toast.error("Failed to delete thumbnails")
    } finally {
      setLoading("deleteThumbnails", false)
    }
  }

  const handleRegenerateThumbnails = async () => {
    setLoading("regenerateThumbnails", true)
    try {
      const response = await fetch(`/api/timelapses/${timelapse.id}/thumbnails/regenerate`, {
        method: "POST",
      })

      if (!response.ok) {
        throw new Error("Failed to regenerate thumbnails")
      }

      toast.success("Thumbnail regeneration started")
      onDataChange?.()
    } catch (error) {
      console.error("Failed to regenerate thumbnails:", error)
      toast.error("Failed to start thumbnail regeneration")
    } finally {
      setLoading("regenerateThumbnails", false)
    }
  }

  const ActionButton = ({ 
    action, 
    icon: Icon, 
    label, 
    description, 
    colorTheme = "cyan",
    variant = "default",
    onClick 
  }: {
    action: string
    icon: any
    label: string
    description: string
    colorTheme?: "cyan" | "purple" | "green" | "red" | "yellow"
    variant?: "default" | "destructive"
    onClick: () => void
  }) => {
    const isLoading = loadingStates[action]
    
    const colorClasses = {
      cyan: "bg-cyan/10 border-cyan/30 hover:bg-cyan/20 text-cyan",
      purple: "bg-purple/10 border-purple/30 hover:bg-purple/20 text-purple",
      green: "bg-green-500/10 border-green-500/30 hover:bg-green-500/20 text-green-400",
      red: "bg-red-500/10 border-red-500/30 hover:bg-red-500/20 text-red-400",
      yellow: "bg-yellow/10 border-yellow/30 hover:bg-yellow/20 text-yellow",
    }

    return (
      <Button
        onClick={onClick}
        disabled={isLoading}
        variant="outline"
        className={cn(
          "w-full h-auto p-4 flex flex-col items-start space-y-2 transition-all duration-300",
          variant === "destructive" ? colorClasses.red : colorClasses[colorTheme]
        )}
      >
        <div className="flex items-center gap-3 w-full">
          {isLoading ? (
            <RefreshCw className="w-5 h-5 animate-spin" />
          ) : (
            <Icon className="w-5 h-5" />
          )}
          <span className="font-medium text-left flex-1">{label}</span>
        </div>
        <p className="text-sm opacity-80 text-left w-full">{description}</p>
      </Button>
    )
  }

  return (
    <div className="space-y-6">
      {/* Video Actions */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Video className="w-4 h-4 text-cyan" />
          <Label className="text-white font-medium">Video Actions</Label>
        </div>
        <div className="space-y-3">
          <ActionButton
            action="generateVideo"
            icon={Play}
            label="Generate Video"
            description="Create a new video from current timelapse images"
            colorTheme="cyan"
            onClick={handleGenerateVideo}
          />
          
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <div>
                <ActionButton
                  action="deleteAllVideos"
                  icon={Trash2}
                  label="Delete All Videos"
                  description="Remove all generated videos for this timelapse"
                  variant="destructive"
                  onClick={() => {}} // Handled by AlertDialog
                />
              </div>
            </AlertDialogTrigger>
            <AlertDialogContent className="glass-strong border-red-500/50">
              <AlertDialogHeader>
                <AlertDialogTitle className="text-white flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-red-400" />
                  Delete All Videos
                </AlertDialogTitle>
                <AlertDialogDescription className="text-gray-300">
                  This will permanently delete all videos generated from this timelapse. 
                  This action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel className="border-gray-600 text-white hover:bg-gray-800">
                  Cancel
                </AlertDialogCancel>
                <AlertDialogAction 
                  onClick={handleDeleteAllVideos}
                  className="bg-red-500 hover:bg-red-600 text-white"
                >
                  Delete All Videos
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {/* Overlay Actions */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-purple" />
          <Label className="text-white font-medium">Overlay Actions</Label>
        </div>
        <div className="space-y-3">
          <ActionButton
            action="reprocessOverlays"
            icon={RefreshCw}
            label="Re-process Overlays"
            description="Regenerate overlays for all images in this timelapse"
            colorTheme="purple"
            onClick={handleReprocessOverlays}
          />
        </div>
      </div>

      {/* Thumbnail Actions */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Image className="w-4 h-4 text-green-400" />
          <Label className="text-white font-medium">Thumbnail Actions</Label>
        </div>
        <div className="space-y-3">
          <ActionButton
            action="regenerateThumbnails"
            icon={RefreshCw}
            label="Regenerate Thumbnails"
            description="Recreate all thumbnails for this timelapse"
            colorTheme="green"
            onClick={handleRegenerateThumbnails}
          />
          
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <div>
                <ActionButton
                  action="deleteThumbnails"
                  icon={Trash2}
                  label="Delete Thumbnails"
                  description="Remove all thumbnail files for this timelapse"
                  variant="destructive"
                  onClick={() => {}} // Handled by AlertDialog
                />
              </div>
            </AlertDialogTrigger>
            <AlertDialogContent className="glass-strong border-red-500/50">
              <AlertDialogHeader>
                <AlertDialogTitle className="text-white flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-red-400" />
                  Delete Thumbnails
                </AlertDialogTitle>
                <AlertDialogDescription className="text-gray-300">
                  This will permanently delete all thumbnail files for this timelapse. 
                  You can regenerate them later if needed.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel className="border-gray-600 text-white hover:bg-gray-800">
                  Cancel
                </AlertDialogCancel>
                <AlertDialogAction 
                  onClick={handleDeleteThumbnails}
                  className="bg-red-500 hover:bg-red-600 text-white"
                >
                  Delete Thumbnails
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-red-400" />
          <Label className="text-white font-medium">Danger Zone</Label>
        </div>
        <div className="p-4 bg-red-500/5 border border-red-500/20 rounded-lg">
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <div>
                <ActionButton
                  action="deleteTimelapse"
                  icon={Trash2}
                  label="Delete Timelapse"
                  description="Permanently delete this entire timelapse and all associated data"
                  variant="destructive"
                  onClick={() => {}} // Handled by AlertDialog
                />
              </div>
            </AlertDialogTrigger>
            <AlertDialogContent className="glass-strong border-red-500/50">
              <AlertDialogHeader>
                <AlertDialogTitle className="text-white flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-red-400" />
                  Delete Timelapse
                </AlertDialogTitle>
                <AlertDialogDescription className="text-gray-300">
                  This will permanently delete the entire timelapse "{timelapse.name}" including:
                  <ul className="mt-2 ml-4 list-disc space-y-1">
                    <li>All {timelapse.image_count} images</li>
                    <li>All generated videos</li>
                    <li>All thumbnails and metadata</li>
                    <li>All overlay data</li>
                  </ul>
                  <br />
                  <strong>This action cannot be undone.</strong>
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel className="border-gray-600 text-white hover:bg-gray-800">
                  Cancel
                </AlertDialogCancel>
                <AlertDialogAction 
                  onClick={handleDeleteTimelapse}
                  className="bg-red-500 hover:bg-red-600 text-white"
                >
                  Delete Timelapse
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>
    </div>
  )
}