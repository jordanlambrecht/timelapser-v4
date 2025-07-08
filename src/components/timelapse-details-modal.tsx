// src/components/timelapse-details-modal.tsx
"use client"

import { useState, useEffect, useCallback, memo } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { VideoPlayer } from "@/components/ui/video-player"
import { ImageThumbnail } from "@/components/ui/image-thumbnail"
import { StatsGrid, StatItem } from "@/components/ui/stats-grid"
import { ActionButtonGroup } from "@/components/ui/action-button-group"
import { useThumbnailProgress } from "@/hooks/use-thumbnail-progress"
import {
  GlassTable,
  GlassTableHeader,
  GlassTableHeaderCell,
  GlassTableBody,
  SelectableTableRow,
  GlassTableCell,
} from "@/components/ui/glass-table"
import { VideoGenerationSettings } from "@/components/video-generation-settings"
import { StatusBadge } from "@/components/ui/status-badge"
import {
  Video,
  Camera,
  Image as ImageIcon,
  Calendar,
  Clock,
  HardDrive,
  Download,
  Edit3,
  Trash2,
  Archive,
  RefreshCw,
  Settings,
  Play,
  Loader2,
  Search,
  Filter,
  ChevronDown,
  Check,
  X,
  AlertTriangle,
  FileVideo,
  Zap,
  Layers,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "@/lib/toast"
import { formatDuration, formatDate } from "@/lib/time-utils"
import type {
  TimelapseDetails,
  TimelapseVideo,
  TimelapseImage,
  TimelapseDetailsModalProps,
} from "@/types"

// Utility function for file size formatting
const formatFileSize = (bytes: number | null | undefined): string => {
  if (!bytes || bytes === 0) return "0 Bytes"
  const k = 1024
  const sizes = ["Bytes", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
}

// Simple video status badge component
const VideoStatusBadge = ({
  status,
}: {
  status: "completed" | "generating" | "failed"
}) => {
  const statusClasses = {
    completed: "bg-green-500/20 text-green-400 border-green-500/30",
    generating: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
    failed: "bg-red-500/20 text-red-400 border-red-500/30",
  }

  return (
    <div
      className={`inline-flex items-center space-x-1 text-xs font-medium px-2 py-1 rounded-full border ${statusClasses[status]}`}
    >
      <span className='capitalize'>{status}</span>
    </div>
  )
}

export const TimelapseDetailsModal = memo(
  function TimelapseDetailsModal({
    isOpen,
    onClose,
    timelapseId,
    cameraName,
    onDataUpdate,
  }: TimelapseDetailsModalProps) {
    // Main data states
    const [timelapse, setTimelapse] = useState<TimelapseDetails | null>(null)
    const [videos, setVideos] = useState<TimelapseVideo[]>([])
    const [images, setImages] = useState<TimelapseImage[]>([])
    const [selectedVideo, setSelectedVideo] = useState<TimelapseVideo | null>(
      null
    )

    // Loading states
    const [loading, setLoading] = useState(true)
    const [imagesLoading, setImagesLoading] = useState(false)
    const [actionLoading, setActionLoading] = useState<string | null>(null)

    // Image management states
    const [selectedImages, setSelectedImages] = useState<Set<number>>(new Set())
    const [lastSelectedIndex, setLastSelectedIndex] = useState<number | null>(
      null
    )
    const [imagesPage, setImagesPage] = useState(1)
    const [imagesSearch, setImagesSearch] = useState("")
    const [hasMoreImages, setHasMoreImages] = useState(true)
    const imagesPerPage = 50

    // Modal states
    const [activeTab, setActiveTab] = useState("overview")
    const [editingName, setEditingName] = useState(false)
    const [newName, setNewName] = useState("")
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
    const [showImageDeleteConfirm, setShowImageDeleteConfirm] = useState(false)
    const [showVideoRegenConfirm, setShowVideoRegenConfirm] = useState(false)
    const [showThumbnailRegenConfirm, setShowThumbnailRegenConfirm] = useState(false)
    const [editingVideoSettings, setEditingVideoSettings] = useState(false)
    const [videoSettings, setVideoSettings] = useState<any>(null)
    
    // Thumbnail states
    const [thumbnailStats, setThumbnailStats] = useState<{
      thumbnail_count: number
      small_count: number
      total_images: number
    } | null>(null)
    // Use custom hook for thumbnail progress tracking
    const { progress: thumbnailProgress, isActive: thumbnailJobActive, startTracking: startThumbnailTracking } = useThumbnailProgress({
      timelapseId: typeof timelapseId === 'number' ? timelapseId : undefined,
      onComplete: () => {
        // Refresh data when thumbnail regeneration completes
        fetchTimelapseData()
        setActionLoading(null)
      },
      onError: (error: string) => {
        // Handle errors
        console.error('Thumbnail regeneration error:', error)
        setActionLoading(null)
      }
    })

    // Fetch timelapse details and videos
    const fetchTimelapseData = useCallback(async () => {
      if (!isOpen || !timelapseId) return

      try {
        setLoading(true)

        // Fetch timelapse details
        const timelapseResponse = await fetch(`/api/timelapses/${timelapseId}`)
        if (!timelapseResponse.ok) throw new Error("Failed to fetch timelapse")
        const timelapseData = await timelapseResponse.json()
        setTimelapse(timelapseData)
        setNewName(timelapseData.name || "")

        // Initialize video settings from timelapse
        setVideoSettings({
          video_generation_mode:
            timelapseData.video_generation_mode || "standard",
          standard_fps: timelapseData.standard_fps || 12,
          enable_time_limits: timelapseData.enable_time_limits || false,
          min_time_seconds: timelapseData.min_time_seconds,
          max_time_seconds: timelapseData.max_time_seconds,
          target_time_seconds: timelapseData.target_time_seconds,
          fps_bounds_min: timelapseData.fps_bounds_min || 1,
          fps_bounds_max: timelapseData.fps_bounds_max || 60,
        })

        // Fetch videos for this timelapse
        const videosResponse = await fetch(
          `/api/timelapses/${timelapseId}/videos`
        )
        if (videosResponse.ok) {
          const videosData = await videosResponse.json()
          setVideos(videosData)

          // Auto-select first completed video
          const completedVideo = videosData.find(
            (v: TimelapseVideo) => v.status === "completed"
          )
          if (completedVideo) {
            setSelectedVideo(completedVideo)
          }
        }

        // Fetch thumbnail statistics for this timelapse
        try {
          const thumbnailStatsResponse = await fetch(
            `/api/timelapses/${timelapseId}/thumbnails/stats`
          )
          if (thumbnailStatsResponse.ok) {
            const thumbnailStatsData = await thumbnailStatsResponse.json()
            setThumbnailStats(thumbnailStatsData)
          }
        } catch (error) {
          console.warn("Failed to fetch thumbnail stats:", error)
        }
      } catch (error) {
        console.error("Error fetching timelapse data:", error)
        toast.error("Failed to load timelapse details")
      } finally {
        setLoading(false)
      }
    }, [isOpen, timelapseId])

    // Fetch images with pagination and search
    const fetchImages = useCallback(
      async (page = 1, search = "", append = false) => {
        if (!timelapseId) return

        try {
          setImagesLoading(true)

          const params = new URLSearchParams({
            page: page.toString(),
            per_page: imagesPerPage.toString(),
            ...(search && { search }),
          })

          const response = await fetch(
            `/api/timelapses/${timelapseId}/images?${params}`
          )
          if (!response.ok) throw new Error("Failed to fetch images")

          const data = await response.json()

          if (append) {
            setImages((prev) => [...prev, ...data.images])
          } else {
            setImages(data.images)
            setSelectedImages(new Set()) // Clear selection on new search
          }

          setHasMoreImages(data.images.length === imagesPerPage)
        } catch (error) {
          console.error("Error fetching images:", error)
          toast.error("Failed to load images")
        } finally {
          setImagesLoading(false)
        }
      },
      [timelapseId, imagesPerPage]
    )

    // Load more images (pagination)
    const loadMoreImages = () => {
      if (!imagesLoading && hasMoreImages) {
        const nextPage = imagesPage + 1
        setImagesPage(nextPage)
        fetchImages(nextPage, imagesSearch, true)
      }
    }

    // Search images
    const searchImages = (search: string) => {
      setImagesSearch(search)
      setImagesPage(1)
      fetchImages(1, search, false)
    }

    // Initial data load with ID validation - remove dependency on fetchTimelapseData
    useEffect(() => {
      if (!isOpen || !timelapseId || typeof timelapseId !== "number") {
        if (isOpen && (!timelapseId || typeof timelapseId !== "number")) {
          toast.error("Invalid timelapse ID")
        }
        return
      }

      // Only fetch data when modal opens or timelapseId changes
      fetchTimelapseData()
    }, [isOpen, timelapseId]) // Removed fetchTimelapseData dependency

    // Load images when switching to images tab
    useEffect(() => {
      if (activeTab === "images" && images.length === 0) {
        fetchImages()
      }
    }, [activeTab, images.length]) // Removed fetchImages from dependencies

    // Reset images when modal closes to prevent stale state
    useEffect(() => {
      if (!isOpen) {
        setImages([])
        setSelectedImages(new Set())
        setLastSelectedIndex(null)
        setImagesPage(1)
        setImagesSearch("")
        setHasMoreImages(true)
        setActiveTab("overview") // Reset to overview tab
      }
    }, [isOpen])

    // Thumbnail progress is now handled by the custom hook

    // Custom selectable row with shift-click support
    const ShiftSelectableTableRow = ({
      children,
      isSelected,
      onSelectionChange,
      imageId,
    }: {
      children: React.ReactNode
      isSelected: boolean
      onSelectionChange: (selected: boolean, isShiftClick?: boolean) => void
      imageId: number
    }) => {
      const handleRowClick = (e: React.MouseEvent) => {
        // Check for shift key and prevent default behavior
        if (e.shiftKey) {
          e.preventDefault()
          onSelectionChange(true, true) // Always select when shift-clicking
        } else {
          // Toggle selection on normal click
          onSelectionChange(!isSelected, false)
        }
      }

      const handleCheckboxChange = (checked: boolean) => {
        onSelectionChange(checked, false)
      }

      return (
        <tr
          className={cn(
            "border-b border-purple-muted/10 transition-all duration-200",
            "hover:bg-purple/5 hover:shadow-lg hover:shadow-purple/10",
            "cursor-pointer",
            isSelected && "bg-cyan/10 border-cyan/30"
          )}
          onClick={handleRowClick}
        >
          <td className='px-3 py-2 w-10'>
            <Checkbox
              checked={isSelected}
              onCheckedChange={handleCheckboxChange}
              className='border-cyan/50 data-[state=checked]:bg-cyan data-[state=checked]:border-cyan'
              onClick={(e: React.MouseEvent) => e.stopPropagation()}
            />
          </td>
          {children}
        </tr>
      )
    }

    // Memoized the image components to prevent unnecessary re-renders
    const MemoizedImageRow = memo(
      ({ image }: { image: TimelapseImage }) => (
        <ShiftSelectableTableRow
          imageId={image.id}
          isSelected={selectedImages.has(image.id)}
          onSelectionChange={(selected, isShiftClick) =>
            handleImageSelection(image.id, selected, isShiftClick)
          }
        >
          <GlassTableCell className='w-20'>
            <ImageThumbnail
              imageId={image.id}
              src={`/api/images/${image.id}/thumbnail`}
              alt={`Image ${image.id}`}
              capturedAt={image.captured_at}
              fileName={
                image.file_path?.split("/").pop() || `Image ${image.id}`
              }
              fileSize={image.file_size || 0}
              className='w-12 h-12'
              showActions={false}
              isSelected={selectedImages.has(image.id)}
            />
          </GlassTableCell>
          <GlassTableCell>
            <div className='font-medium text-white'>
              {image.file_path?.split("/").pop() || `Image ${image.id}`}
            </div>
          </GlassTableCell>
          <GlassTableCell>
            <div className='text-sm text-grey-light/70'>
              {formatDate(image.captured_at)}
            </div>
          </GlassTableCell>
          <GlassTableCell>
            <div className='text-sm text-yellow font-medium'>
              Day {image.day_number}
            </div>
          </GlassTableCell>
          <GlassTableCell>
            <div className='text-sm text-grey-light/70'>
              {formatFileSize(image.file_size)}
            </div>
          </GlassTableCell>
          <GlassTableCell className='w-24'>
            <div className='flex items-center space-x-2'>
              <Button
                onClick={() => handleImageDownload(image)}
                size='sm'
                variant='ghost'
                className='h-8 w-8 p-0 hover:bg-cyan/20 text-cyan'
                title='Download'
              >
                <Download className='w-4 h-4' />
              </Button>
              <Button
                onClick={() => {
                  setSelectedImages(new Set([image.id]))
                  setShowImageDeleteConfirm(true)
                }}
                size='sm'
                variant='ghost'
                className='h-8 w-8 p-0 hover:bg-red-500/20 text-red-400'
                title='Delete'
              >
                <Trash2 className='w-4 h-4' />
              </Button>
            </div>
          </GlassTableCell>
        </ShiftSelectableTableRow>
      ),
      (prevProps, nextProps) => {
        return (
          prevProps.image.id === nextProps.image.id &&
          prevProps.image.captured_at === nextProps.image.captured_at &&
          prevProps.image.file_size === nextProps.image.file_size
        )
      }
    )

    // Action handlers
    const handleRename = async () => {
      if (!timelapse || !newName.trim()) return

      try {
        setActionLoading("rename")
        const response = await fetch(`/api/timelapses/${timelapseId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: newName.trim() }),
        })

        if (!response.ok) throw new Error("Failed to rename timelapse")

        setTimelapse((prev) =>
          prev ? { ...prev, name: newName.trim() } : null
        )
        setEditingName(false)
        toast.success("Timelapse renamed successfully")
      } catch (error) {
        console.error("Error renaming timelapse:", error)
        toast.error("Failed to rename timelapse")
      } finally {
        setActionLoading(null)
      }
    }

    const handleDelete = async () => {
      try {
        setActionLoading("delete")
        const response = await fetch(`/api/timelapses/${timelapseId}`, {
          method: "DELETE",
        })

        if (!response.ok) throw new Error("Failed to delete timelapse")

        toast.success("Timelapse deleted successfully")
        onClose()
      } catch (error) {
        console.error("Error deleting timelapse:", error)
        toast.error("Failed to delete timelapse")
        setActionLoading(null)
      }
    }

    const handleArchive = async () => {
      if (!timelapse) return

      try {
        setActionLoading("archive")
        const newStatus =
          timelapse.status === "archived" ? "completed" : "archived"

        const response = await fetch(`/api/timelapses/${timelapseId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: newStatus }),
        })

        if (!response.ok) throw new Error("Failed to archive timelapse")

        setTimelapse((prev) =>
          prev ? { ...prev, status: newStatus as any } : null
        )
        toast.success(
          `Timelapse ${
            newStatus === "archived" ? "archived" : "unarchived"
          } successfully`
        )
      } catch (error) {
        console.error("Error archiving timelapse:", error)
        toast.error("Failed to archive timelapse")
      } finally {
        setActionLoading(null)
      }
    }

    const handleRegenerateVideo = async () => {
      try {
        setActionLoading("regenerate")
        const response = await fetch(
          `/api/timelapses/${timelapseId}/regenerate-video`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              settings: videoSettings,
              name: `${
                timelapse?.name || "timelapse"
              }_regenerated_${new Date().getTime()}`,
            }),
          }
        )

        if (!response.ok) throw new Error("Failed to start video regeneration")

        toast.success("Video regeneration started")
        setShowVideoRegenConfirm(false)

        // Refresh videos list
        fetchTimelapseData()
      } catch (error) {
        console.error("Error regenerating video:", error)
        toast.error("Failed to start video regeneration")
      } finally {
        setActionLoading(null)
      }
    }

    const handleRegenerateThumbnails = async () => {
      try {
        setActionLoading("regenerate-thumbnails")
        const response = await fetch(
          `/api/timelapses/${timelapseId}/thumbnails/regenerate`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
          }
        )

        if (!response.ok) throw new Error("Failed to start thumbnail regeneration")

        const result = await response.json()
        
        // Start progress tracking using the custom hook
        startThumbnailTracking(result.jobs_created || 0)
        
        toast.success(`Thumbnail regeneration started for ${result.jobs_created} images`)
        setShowThumbnailRegenConfirm(false)

        // Note: Loading state will be cleared when all jobs complete via the custom hook's onComplete callback
        // Don't refresh data immediately - let SSE handle real-time updates
      } catch (error) {
        console.error("Error regenerating thumbnails:", error)
        toast.error("Failed to start thumbnail regeneration")
        setActionLoading(null) // Clear loading state on error
      }
    }

    const handleDeleteSelectedImages = async () => {
      if (selectedImages.size === 0) return

      try {
        setActionLoading("deleteImages")
        const imageIds = Array.from(selectedImages)

        const response = await fetch(`/api/images/bulk-delete`, {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image_ids: imageIds }),
        })

        if (!response.ok) throw new Error("Failed to delete images")

        // Remove deleted images from local state
        setImages((prev) => prev.filter((img) => !selectedImages.has(img.id)))
        setSelectedImages(new Set())
        setShowImageDeleteConfirm(false)

        toast.success(`${imageIds.length} images deleted successfully`)

        // Ask about video regeneration
        setShowVideoRegenConfirm(true)
      } catch (error) {
        console.error("Error deleting images:", error)
        toast.error("Failed to delete images")
      } finally {
        setActionLoading(null)
      }
    }

    const handleImageSelection = (
      imageId: number,
      selected: boolean,
      isShiftClick?: boolean
    ) => {
      setSelectedImages((prev) => {
        const newSelection = new Set(prev)
        const currentIndex = images.findIndex((img) => img.id === imageId)

        if (isShiftClick && lastSelectedIndex !== null && currentIndex !== -1) {
          // Range selection with shift-click
          const startIndex = Math.min(lastSelectedIndex, currentIndex)
          const endIndex = Math.max(lastSelectedIndex, currentIndex)

          // Clear any existing selection first for clean range selection
          const rangesToSelect = []
          for (let i = startIndex; i <= endIndex; i++) {
            if (images[i]) {
              rangesToSelect.push(images[i].id)
            }
          }

          // If all items in range are already selected, deselect them
          const allRangeSelected = rangesToSelect.every((id) =>
            newSelection.has(id)
          )

          if (allRangeSelected) {
            // Deselect the range
            rangesToSelect.forEach((id) => newSelection.delete(id))
          } else {
            // Select the range
            rangesToSelect.forEach((id) => newSelection.add(id))
          }
        } else {
          // Normal single selection
          if (selected) {
            newSelection.add(imageId)
          } else {
            newSelection.delete(imageId)
          }
          // Update last selected index for future range selections
          setLastSelectedIndex(currentIndex)
        }

        return newSelection
      })
    }

    const handleSelectAllImages = () => {
      if (selectedImages.size === images.length) {
        setSelectedImages(new Set())
        setLastSelectedIndex(null)
      } else {
        setSelectedImages(new Set(images.map((img) => img.id)))
        setLastSelectedIndex(images.length - 1) // Set to last image when selecting all
      }
    }

    const getImageThumbnailSrc = (image: TimelapseImage) => {
      if (image.thumbnail_path) {
        return `/api/images/${image.id}/thumbnail`
      }
      return `/api/images/${image.id}/small`
    }

    const getImageFullSrc = (image: TimelapseImage) => {
      return `/api/images/${image.id}/download`
    }

    const handleVideoDownload = (video: TimelapseVideo) => {
      window.open(`/api/videos/${video.id}/download`, "_blank")
    }

    const handleImageDownload = (image: TimelapseImage) => {
      window.open(`/api/images/${image.id}/download`, "_blank")
    }

    const handleBulkImageDownload = async () => {
      if (selectedImages.size === 0) {
        toast.error("No images selected")
        return
      }

      try {
        setActionLoading("bulk-download")

        const imageIds = Array.from(selectedImages)

        // Create the request
        const response = await fetch("/api/images/bulk/download", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ image_ids: imageIds }),
        })

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        // Get the blob data
        const blob = await response.blob()

        // Create download link
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.href = url
        a.download = `timelapse_${timelapseId}_images_${imageIds.length}.zip`
        document.body.appendChild(a)
        a.click()

        // Cleanup
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)

        toast.success(`Downloaded ${imageIds.length} images as ZIP file`)
      } catch (error) {
        console.error("Bulk download error:", error)
        toast.error("Failed to download images")
      } finally {
        setActionLoading(null)
      }
    }

    const getTimelapseDisplayName = () => {
      return timelapse?.name || `Timelapse ${timelapseId}`
    }

    if (!isOpen) return null

    return (
      <>
        <Dialog open={isOpen} onOpenChange={onClose}>
          <DialogContent className='max-w-8xl max-h-[95vh] glass-strong border-purple-muted/50 overflow-hidden'>
            <DialogHeader className='relative'>
              <div className='absolute -top-2 -right-2 w-16 h-16 bg-gradient-to-bl from-cyan/10 to-transparent rounded-full' />
              <DialogTitle className='flex items-center justify-between'>
                <div className='flex items-center space-x-3'>
                  <div className='p-2 bg-gradient-to-br from-cyan/20 to-purple/20 rounded-xl'>
                    <Video className='w-6 h-6 text-white' />
                  </div>

                  {editingName ? (
                    <div className='flex items-center space-x-2'>
                      <Input
                        value={newName}
                        onChange={(e) => setNewName(e.target.value)}
                        className='h-8 bg-black/30 border-purple-muted/30 text-white'
                        autoFocus
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleRename()
                          if (e.key === "Escape") setEditingName(false)
                        }}
                      />
                      <Button
                        onClick={handleRename}
                        size='sm'
                        disabled={actionLoading === "rename"}
                        className='h-8 w-8 p-0 bg-success/20 hover:bg-success/30 text-success'
                      >
                        {actionLoading === "rename" ? (
                          <Loader2 className='w-4 h-4 animate-spin' />
                        ) : (
                          <Check className='w-4 h-4' />
                        )}
                      </Button>
                      <Button
                        onClick={() => setEditingName(false)}
                        size='sm'
                        className='h-8 w-8 p-0 bg-failure/20 hover:bg-failure/30 text-failure'
                      >
                        <X className='w-4 h-4' />
                      </Button>
                    </div>
                  ) : (
                    <div className='flex items-center space-x-2'>
                      <span className='text-xl text-white'>
                        {getTimelapseDisplayName()}
                      </span>
                      <Button
                        onClick={() => setEditingName(true)}
                        size='sm'
                        variant='ghost'
                        className='h-8 w-8 p-0 hover:bg-purple/20 text-purple-light/70 hover:text-purple-light'
                      >
                        <Edit3 className='w-4 h-4' />
                      </Button>
                    </div>
                  )}
                </div>

                {timelapse && (
                  <div className='flex items-center space-x-2'>
                    <StatusBadge
                      healthStatus='online'
                      timelapseStatus={timelapse.status}
                      className='text-sm'
                    />

                    <ActionButtonGroup
                      actions={[
                        {
                          icon: Archive,
                          label:
                            timelapse.status === "archived"
                              ? "Unarchive"
                              : "Archive",
                          onClick: handleArchive,
                          variant: "warning",
                          disabled: actionLoading === "archive",
                        },
                        {
                          icon: Layers,
                          label: "Regenerate Thumbnails",
                          onClick: () => setShowThumbnailRegenConfirm(true),
                          disabled: actionLoading === "regenerate-thumbnails",
                        },
                        {
                          icon: RefreshCw,
                          label: "Regenerate Video",
                          onClick: () => setShowVideoRegenConfirm(true),
                          disabled: actionLoading === "regenerate",
                        },
                        {
                          icon: Trash2,
                          label: "Delete Timelapse",
                          onClick: () => setShowDeleteConfirm(true),
                          variant: "destructive",
                          disabled: !!actionLoading,
                        },
                      ]}
                      variant='mixed'
                      primaryActions={1}
                    />
                  </div>
                )}
              </DialogTitle>
            </DialogHeader>

            {loading ? (
              <div className='flex items-center justify-center py-20'>
                <div className='text-center space-y-4'>
                  <Loader2 className='w-12 h-12 text-cyan animate-spin mx-auto' />
                  <p className='text-grey-light/60'>
                    Loading timelapse details...
                  </p>
                </div>
              </div>
            ) : !timelapse ? (
              <div className='flex items-center justify-center py-20'>
                <div className='text-center space-y-4'>
                  <AlertTriangle className='w-12 h-12 text-yellow mx-auto' />
                  <p className='text-white'>Timelapse not found</p>
                </div>
              </div>
            ) : (
              <Tabs
                value={activeTab}
                onValueChange={setActiveTab}
                className='space-y-6'
              >
                <TabsList className='grid w-full grid-cols-4 bg-black/20 border border-purple-muted/30'>
                  <TabsTrigger
                    value='overview'
                    className='data-[state=active]:bg-cyan/20 data-[state=active]:text-cyan'
                  >
                    Overview
                  </TabsTrigger>
                  <TabsTrigger
                    value='videos'
                    className='data-[state=active]:bg-purple/20 data-[state=active]:text-purple'
                  >
                    Videos ({videos.length})
                  </TabsTrigger>
                  <TabsTrigger
                    value='images'
                    className='data-[state=active]:bg-yellow/20 data-[state=active]:text-yellow'
                  >
                    Images ({timelapse.image_count})
                  </TabsTrigger>
                  <TabsTrigger
                    value='settings'
                    className='data-[state=active]:bg-pink/20 data-[state=active]:text-pink'
                  >
                    Settings
                  </TabsTrigger>
                </TabsList>

                <div className='max-h-[calc(80vh-200px)] overflow-y-auto'>
                  <TabsContent value='overview' className='space-y-6 mt-0'>
                    {/* Stats Grid */}
                    <StatsGrid columns={5}>
                      <StatItem
                        icon={ImageIcon}
                        label='Total Images'
                        value={timelapse.image_count}
                        accent='cyan'
                      />
                      <StatItem
                        icon={FileVideo}
                        label='Videos Generated'
                        value={videos.length}
                        accent='purple'
                      />
                      <StatItem
                        icon={Layers}
                        label='Thumbnail Coverage'
                        value={thumbnailStats ? `${Math.round((thumbnailStats.thumbnail_count / Math.max(thumbnailStats.total_images, 1)) * 100)}%` : "Loading..."}
                        accent='pink'
                      />
                      <StatItem
                        icon={Calendar}
                        label='Start Date'
                        value={formatDate(
                          timelapse.start_date || timelapse.created_at
                        )}
                        accent='yellow'
                      />
                      <StatItem
                        icon={Clock}
                        label='Last Capture'
                        value={
                          timelapse.last_capture_at
                            ? formatDate(timelapse.last_capture_at)
                            : "Never"
                        }
                        accent='success'
                      />
                    </StatsGrid>

                    {/* Video Player Section */}
                    {selectedVideo ? (
                      <div className='space-y-4'>
                        <h3 className='text-lg font-bold text-white flex items-center space-x-2'>
                          <Play className='w-5 h-5 text-cyan' />
                          <span>Video Player</span>
                        </h3>

                        <VideoPlayer
                          src={`/api/videos/${selectedVideo.id}/download`}
                          title={selectedVideo.name}
                          className='aspect-video'
                          showDownload
                          onDownload={() => handleVideoDownload(selectedVideo)}
                        />

                        {/* Video Details */}
                        <div className='glass p-4 rounded-xl border border-purple-muted/20'>
                          <div className='grid grid-cols-2 md:grid-cols-4 gap-4 text-sm'>
                            <div>
                              <span className='text-grey-light/70'>
                                Duration:
                              </span>
                              <div className='text-white font-medium'>
                                {formatDuration(
                                  selectedVideo.duration_seconds || 0
                                )}
                              </div>
                            </div>
                            <div>
                              <span className='text-grey-light/70'>
                                File Size:
                              </span>
                              <div className='text-white font-medium'>
                                {formatFileSize(selectedVideo.file_size)}
                              </div>
                            </div>
                            <div>
                              <span className='text-grey-light/70'>FPS:</span>
                              <div className='text-white font-medium'>
                                {selectedVideo.calculated_fps?.toFixed(2) ||
                                  "N/A"}
                              </div>
                            </div>
                            <div>
                              <span className='text-grey-light/70'>
                                Status:
                              </span>
                              <div>
                                <VideoStatusBadge
                                  status={selectedVideo.status}
                                />
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className='text-center py-12 glass rounded-xl border border-purple-muted/20'>
                        <FileVideo className='w-16 h-16 text-grey-light/30 mx-auto mb-4' />
                        <h3 className='text-lg font-bold text-white mb-2'>
                          No Videos Available
                        </h3>
                        <p className='text-grey-light/60 mb-4'>
                          Generate a video from this timelapse to start playback
                        </p>
                        <Button
                          onClick={() => setShowVideoRegenConfirm(true)}
                          className='bg-gradient-to-r from-cyan to-purple hover:from-cyan-dark hover:to-purple-dark text-black font-medium'
                        >
                          <Video className='w-4 h-4 mr-2' />
                          Generate Video
                        </Button>
                      </div>
                    )}
                  </TabsContent>

                  <TabsContent value='videos' className='space-y-4 mt-0'>
                    <div className='flex items-center justify-between'>
                      <h3 className='text-lg font-bold text-white flex items-center space-x-2'>
                        <FileVideo className='w-5 h-5 text-purple' />
                        <span>Generated Videos ({videos.length})</span>
                      </h3>

                      <Button
                        onClick={() => setShowVideoRegenConfirm(true)}
                        size='sm'
                        className='bg-gradient-to-r from-cyan to-purple hover:from-cyan-dark hover:to-purple-dark text-black font-medium'
                      >
                        <Video className='w-4 h-4 mr-2' />
                        Generate New Video
                      </Button>
                    </div>

                    {videos.length === 0 ? (
                      <div className='text-center py-12 glass rounded-xl border border-purple-muted/20'>
                        <FileVideo className='w-16 h-16 text-grey-light/30 mx-auto mb-4' />
                        <h4 className='text-lg font-bold text-white mb-2'>
                          No Videos Generated
                        </h4>
                        <p className='text-grey-light/60'>
                          Create your first video from this timelapse
                        </p>
                      </div>
                    ) : (
                      <div className='space-y-3'>
                        {videos.map((video) => (
                          <div
                            key={video.id}
                            className={cn(
                              "p-4 rounded-xl border cursor-pointer transition-all duration-200 glass",
                              selectedVideo?.id === video.id
                                ? "border-purple/50 bg-purple/10"
                                : "border-purple-muted/30 hover:border-purple-muted/50 hover:bg-purple/5"
                            )}
                            onClick={() => setSelectedVideo(video)}
                          >
                            <div className='flex items-center justify-between'>
                              <div className='space-y-2 flex-1'>
                                <div className='flex items-center space-x-3'>
                                  <div
                                    className={cn(
                                      "w-2 h-2 rounded-full",
                                      selectedVideo?.id === video.id
                                        ? "bg-purple"
                                        : "bg-grey-light/30"
                                    )}
                                  />
                                  <h4 className='font-medium text-white'>
                                    {video.name}
                                  </h4>
                                  <VideoStatusBadge status={video.status} />
                                </div>

                                <div className='flex items-center space-x-4 text-sm text-grey-light/70'>
                                  <span>{formatDate(video.created_at)}</span>
                                  <span>•</span>
                                  <span>
                                    {formatDuration(
                                      video.duration_seconds || 0
                                    )}
                                  </span>
                                  <span>•</span>
                                  <span>{formatFileSize(video.file_size)}</span>
                                  {video.calculated_fps && (
                                    <>
                                      <span>•</span>
                                      <span>
                                        {video.calculated_fps.toFixed(2)} FPS
                                      </span>
                                    </>
                                  )}
                                </div>
                              </div>

                              <ActionButtonGroup
                                actions={[
                                  {
                                    icon: Download,
                                    label: "Download",
                                    onClick: () => handleVideoDownload(video),
                                  },
                                  {
                                    icon: Edit3,
                                    label: "Rename",
                                    onClick: () => {
                                      // TODO: Implement video rename
                                    },
                                  },
                                  {
                                    icon: Trash2,
                                    label: "Delete",
                                    onClick: () => {
                                      // TODO: Implement video delete
                                    },
                                    variant: "destructive",
                                  },
                                ]}
                                variant='buttons'
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </TabsContent>

                  <TabsContent value='images' className='space-y-4 mt-0'>
                    {/* Images header with controls */}
                    <div className='flex items-center justify-between'>
                      <div className='flex items-center space-x-4'>
                        <h3 className='text-lg font-bold text-white flex items-center space-x-2'>
                          <ImageIcon className='w-5 h-5 text-yellow' />
                          <span>Captured Images ({timelapse.image_count})</span>
                        </h3>

                        {selectedImages.size > 0 && (
                          <div className='flex items-center space-x-2'>
                            <span className='text-sm text-cyan'>
                              {selectedImages.size} selected
                            </span>
                            <Button
                              onClick={handleBulkImageDownload}
                              size='sm'
                              variant='ghost'
                              disabled={actionLoading === "bulk-download"}
                              className='bg-cyan/20 hover:bg-cyan/30 text-cyan border-cyan/30'
                            >
                              {actionLoading === "bulk-download" ? (
                                <Loader2 className='w-4 h-4 mr-2 animate-spin' />
                              ) : (
                                <Download className='w-4 h-4 mr-2' />
                              )}
                              Download Selected
                            </Button>
                            <Button
                              onClick={() => setShowImageDeleteConfirm(true)}
                              size='sm'
                              variant='destructive'
                              className='bg-red-500/20 hover:bg-red-500/30 text-red-400 border-red-500/30'
                            >
                              <Trash2 className='w-4 h-4 mr-2' />
                              Delete Selected
                            </Button>
                          </div>
                        )}
                      </div>

                      <div className='flex items-center space-x-2'>
                        <div className='relative'>
                          <Search className='absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-grey-light/70' />
                          <Input
                            placeholder='Search images...'
                            value={imagesSearch}
                            onChange={(e) => searchImages(e.target.value)}
                            className='pl-10 w-64 h-9 bg-black/30 border-purple-muted/30 text-white'
                          />
                        </div>
                      </div>
                    </div>

                    {/* Images table */}
                    {images.length === 0 ? (
                      <div className='text-center py-12 glass rounded-xl border border-purple-muted/20'>
                        {imagesLoading ? (
                          <>
                            <Loader2 className='w-12 h-12 text-yellow animate-spin mx-auto mb-4' />
                            <p className='text-grey-light/60'>
                              Loading images...
                            </p>
                          </>
                        ) : (
                          <>
                            <ImageIcon className='w-16 h-16 text-grey-light/30 mx-auto mb-4' />
                            <h4 className='text-lg font-bold text-white mb-2'>
                              No Images Found
                            </h4>
                            <p className='text-grey-light/60'>
                              {imagesSearch
                                ? "Try adjusting your search terms"
                                : "This timelapse has no captured images"}
                            </p>
                          </>
                        )}
                      </div>
                    ) : (
                      <GlassTable variant='compact' className='min-h-[400px]'>
                        <GlassTableHeader sticky>
                          <tr>
                            <GlassTableHeaderCell className='w-10'>
                              <Button
                                onClick={handleSelectAllImages}
                                size='sm'
                                variant='ghost'
                                className='h-6 w-6 p-0 hover:bg-cyan/20'
                              >
                                <Check className='w-4 h-4 text-cyan' />
                              </Button>
                            </GlassTableHeaderCell>
                            <GlassTableHeaderCell className='w-20'>
                              Preview
                            </GlassTableHeaderCell>
                            <GlassTableHeaderCell>Image</GlassTableHeaderCell>
                            <GlassTableHeaderCell>
                              Captured
                            </GlassTableHeaderCell>
                            <GlassTableHeaderCell>Day</GlassTableHeaderCell>
                            <GlassTableHeaderCell>Size</GlassTableHeaderCell>
                            <GlassTableHeaderCell className='w-24'>
                              Actions
                            </GlassTableHeaderCell>
                          </tr>
                        </GlassTableHeader>
                        <GlassTableBody>
                          {images.map((image) => (
                            <MemoizedImageRow
                              key={`image-${image.id}`}
                              image={image}
                            />
                          ))}
                        </GlassTableBody>
                      </GlassTable>
                    )}

                    {/* Load more button */}
                    {hasMoreImages && (
                      <div className='text-center pt-4'>
                        <Button
                          onClick={loadMoreImages}
                          disabled={imagesLoading}
                          variant='outline'
                          className='border-purple-muted/40 hover:bg-purple/20 text-white'
                        >
                          {imagesLoading ? (
                            <>
                              <Loader2 className='w-4 h-4 mr-2 animate-spin' />
                              Loading...
                            </>
                          ) : (
                            <>
                              <ChevronDown className='w-4 h-4 mr-2' />
                              Load More Images
                            </>
                          )}
                        </Button>
                      </div>
                    )}
                  </TabsContent>

                  <TabsContent value='settings' className='space-y-6 mt-0'>
                    <div className='space-y-6'>
                      <h3 className='text-lg font-bold text-white flex items-center space-x-2'>
                        <Settings className='w-5 h-5 text-pink' />
                        <span>Video Generation Settings</span>
                      </h3>

                      {videoSettings && (
                        <VideoGenerationSettings
                          settings={videoSettings}
                          onChange={setVideoSettings}
                          totalImages={timelapse.image_count}
                          showPreview={true}
                          className='glass p-6 rounded-xl border border-purple-muted/30'
                        />
                      )}

                      <div className='flex justify-end space-x-3'>
                        <Button
                          onClick={() => setShowVideoRegenConfirm(true)}
                          className='bg-gradient-to-r from-cyan to-purple hover:from-cyan-dark hover:to-purple-dark text-black font-medium'
                        >
                          <Zap className='w-4 h-4 mr-2' />
                          Apply & Generate Video
                        </Button>
                      </div>
                    </div>
                  </TabsContent>
                </div>
              </Tabs>
            )}
          </DialogContent>
        </Dialog>

        {/* Delete Timelapse Confirmation */}
        <AlertDialog
          open={showDeleteConfirm}
          onOpenChange={setShowDeleteConfirm}
        >
          <AlertDialogContent className='glass-strong border-purple-muted/50'>
            <AlertDialogHeader>
              <AlertDialogTitle className='flex items-center space-x-2'>
                <AlertTriangle className='w-5 h-5 text-red-400' />
                <span>Delete Timelapse</span>
              </AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to delete "{getTimelapseDisplayName()}"?
                This action cannot be undone and will also delete all associated
                images and videos.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className='border-purple-muted/40 hover:bg-purple-muted/20'>
                Cancel
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={handleDelete}
                disabled={actionLoading === "delete"}
                className='bg-red-500/20 hover:bg-red-500/30 text-red-400 border-red-500/30'
              >
                {actionLoading === "delete" ? (
                  <>
                    <Loader2 className='w-4 h-4 mr-2 animate-spin' />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 className='w-4 h-4 mr-2' />
                    Delete Timelapse
                  </>
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Delete Images Confirmation */}
        <AlertDialog
          open={showImageDeleteConfirm}
          onOpenChange={setShowImageDeleteConfirm}
        >
          <AlertDialogContent className='glass-strong border-purple-muted/50'>
            <AlertDialogHeader>
              <AlertDialogTitle className='flex items-center space-x-2'>
                <AlertTriangle className='w-5 h-5 text-red-400' />
                <span>Delete Images</span>
              </AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to delete {selectedImages.size} image
                {selectedImages.size !== 1 ? "s" : ""}? This action cannot be
                undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className='border-purple-muted/40 hover:bg-purple-muted/20'>
                Cancel
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={handleDeleteSelectedImages}
                disabled={actionLoading === "deleteImages"}
                className='bg-red-500/20 hover:bg-red-500/30 text-red-400 border-red-500/30'
              >
                {actionLoading === "deleteImages" ? (
                  <>
                    <Loader2 className='w-4 h-4 mr-2 animate-spin' />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 className='w-4 h-4 mr-2' />
                    Delete {selectedImages.size} Image
                    {selectedImages.size !== 1 ? "s" : ""}
                  </>
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Video Regeneration Confirmation */}
        <AlertDialog
          open={showVideoRegenConfirm}
          onOpenChange={setShowVideoRegenConfirm}
        >
          <AlertDialogContent className='glass-strong border-purple-muted/50'>
            <AlertDialogHeader>
              <AlertDialogTitle className='flex items-center space-x-2'>
                <RefreshCw className='w-5 h-5 text-cyan' />
                <span>Regenerate Video</span>
              </AlertDialogTitle>
              <AlertDialogDescription>
                This will create a new video using the current settings and all
                available images from this timelapse. The process may take
                several minutes.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className='border-purple-muted/40 hover:bg-purple-muted/20'>
                Cancel
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={handleRegenerateVideo}
                disabled={actionLoading === "regenerate"}
                className='bg-gradient-to-r from-cyan to-purple hover:from-cyan-dark hover:to-purple-dark text-black font-medium'
              >
                {actionLoading === "regenerate" ? (
                  <>
                    <Loader2 className='w-4 h-4 mr-2 animate-spin' />
                    Starting...
                  </>
                ) : (
                  <>
                    <Video className='w-4 h-4 mr-2' />
                    Generate Video
                  </>
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Thumbnail Regeneration Confirmation */}
        <AlertDialog
          open={showThumbnailRegenConfirm}
          onOpenChange={setShowThumbnailRegenConfirm}
        >
          <AlertDialogContent className='glass-strong border-purple-muted/50'>
            <AlertDialogHeader>
              <AlertDialogTitle className='flex items-center space-x-2'>
                <Layers className='w-5 h-5 text-pink' />
                <span>Regenerate Thumbnails</span>
              </AlertDialogTitle>
              <AlertDialogDescription>
                This will regenerate thumbnails for all images in this timelapse.
                {thumbnailStats && (
                  <div className="mt-2 text-sm">
                    <strong>Current Status:</strong> {thumbnailStats.thumbnail_count} of {thumbnailStats.total_images} images have thumbnails
                  </div>
                )}
                The process will run in the background and may take several minutes.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel className='border-purple-muted/40 hover:bg-purple-muted/20'>
                Cancel
              </AlertDialogCancel>
              <AlertDialogAction
                onClick={handleRegenerateThumbnails}
                disabled={actionLoading === "regenerate-thumbnails"}
                className='bg-gradient-to-r from-pink to-purple hover:from-pink-dark hover:to-purple-dark text-black font-medium'
              >
                {actionLoading === "regenerate-thumbnails" ? (
                  <>
                    <Loader2 className='w-4 h-4 mr-2 animate-spin' />
                    Starting...
                  </>
                ) : (
                  <>
                    <Layers className='w-4 h-4 mr-2' />
                    Regenerate Thumbnails
                  </>
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </>
    )
  },
  (prevProps, nextProps) => {
    // Only re-render if essential props change
    return (
      prevProps.isOpen === nextProps.isOpen &&
      prevProps.timelapseId === nextProps.timelapseId &&
      prevProps.cameraName === nextProps.cameraName
    )
  }
)
