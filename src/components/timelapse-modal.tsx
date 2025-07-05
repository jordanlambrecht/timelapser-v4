// src/components/timelapse-modal.tsx
import { useState, useEffect } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { StatusBadge } from "@/components/ui/status-badge"
import {
  Play,
  Download,
  Edit3,
  Check,
  X,
  Video as VideoIcon,
  Calendar,
  Clock,
  HardDrive,
  Trash2,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { formatDuration, formatDate } from "@/lib/time-utils"
import { DeleteTimelapseConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { useTimezoneSettings } from "@/contexts/settings-context"
import { toast } from "@/lib/toast"
import { Video } from "@/types"

interface TimelapseModalProps {
  isOpen: boolean
  onClose: () => void
  cameraId: number
  cameraName: string
}

export function TimelapseModal({
  isOpen,
  onClose,
  cameraId,
  cameraName,
}: TimelapseModalProps) {
  const [videos, setVideos] = useState<Video[]>([])
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null)
  const [loading, setLoading] = useState(true)
  const [editingVideoId, setEditingVideoId] = useState<number | null>(null)
  const [editName, setEditName] = useState("")

  // Confirmation dialog state
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false)
  const [videoToDelete, setVideoToDelete] = useState<Video | null>(null)
  const [deleteLoading, setDeleteLoading] = useState(false)

  // Get timezone from settings
  const { timezone } = useTimezoneSettings()

  const fetchVideos = async () => {
    if (!isOpen || !cameraId) return

    try {
      setLoading(true)
      const response = await fetch(`/api/videos?camera_id=${cameraId}`)
      if (response.ok) {
        const data = await response.json()
        const completedVideos = data.filter(
          (v: Video) => v.status === "completed"
        )
        setVideos(completedVideos)

        // Auto-select the first video
        if (completedVideos.length > 0 && !selectedVideo) {
          setSelectedVideo(completedVideos[0])
        }
      }
    } catch (error) {
      console.error("Error fetching videos:", error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchVideos()
  }, [isOpen, cameraId])

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return "Unknown"
    const mb = bytes / (1024 * 1024)
    return `${mb.toFixed(1)} MB`
  }

  const handleDownload = async (video: Video) => {
    try {
      window.open(`/api/videos/${video.id}/download`, "_blank")
    } catch (error) {
      console.error("Error downloading video:", error)
    }
  }

  const handleStartEdit = (video: Video) => {
    setEditingVideoId(video.id)
    // Extract name from file path or use a default
    const fileName =
      video.file_path?.split("/").pop()?.replace(".mp4", "") ||
      `Timelapse-${video.id}`
    setEditName(fileName)
  }

  const handleSaveEdit = async (videoId: number) => {
    if (!editName.trim()) {
      toast.warning("Please enter a valid video name", {
        description: "Video name cannot be empty",
        duration: 4000,
      })
      return
    }

    try {
      const response = await fetch(`/api/videos/${videoId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: editName }),
      })

      if (response.ok) {
        setEditingVideoId(null)
        setEditName("")
        fetchVideos() // Refresh the list

        // Show enhanced success toast
        const oldName =
          videos
            .find((v) => v.id === videoId)
            ?.file_path?.split("/")
            .pop()
            ?.replace(".mp4", "") || "Unknown"
        toast.timelapseRenamed(oldName, editName)
      } else {
        throw new Error("Failed to rename video")
      }
    } catch (error) {
      console.error("Error renaming video:", error)
      toast.error("Failed to rename video", {
        description:
          error instanceof Error ? error.message : "Please try again",
        duration: 6000,
      })
    }
  }

  const handleCancelEdit = () => {
    setEditingVideoId(null)
    setEditName("")
  }

  const handleDelete = async (video: Video) => {
    setVideoToDelete(video)
    setConfirmDeleteOpen(true)
  }

  const confirmDeleteVideo = async () => {
    if (!videoToDelete) return

    setDeleteLoading(true)
    try {
      const videoName = getVideoDisplayName(videoToDelete)
      const response = await fetch(`/api/videos/${videoToDelete.id}`, {
        method: "DELETE",
      })

      if (response.ok) {
        // Show success toast with undo functionality
        toast.timelapseDeleted(videoName, async () => {
          // Note: Video undo is complex since we'd need to regenerate
          // For now, just show a message that undo isn't available for videos
          toast.info("Video undo not available", {
            description:
              "Videos cannot be restored once deleted. You can regenerate them from captured images.",
            duration: 6000,
          })
        })

        // If we deleted the selected video, select another one
        if (selectedVideo?.id === videoToDelete.id) {
          const remainingVideos = videos.filter(
            (v) => v.id !== videoToDelete.id
          )
          setSelectedVideo(
            remainingVideos.length > 0 ? remainingVideos[0] : null
          )
        }

        fetchVideos() // Refresh the list
        setConfirmDeleteOpen(false)
        setVideoToDelete(null)
      } else {
        throw new Error("Failed to delete video")
      }
    } catch (error) {
      console.error("Error deleting video:", error)
      toast.error("Failed to delete video", {
        description:
          error instanceof Error ? error.message : "Please try again",
        duration: 6000,
      })
    } finally {
      setDeleteLoading(false)
    }
  }

  const getVideoDisplayName = (video: Video) => {
    return (
      video.file_path?.split("/").pop()?.replace(".mp4", "") ||
      `Timelapse-${video.id}`
    )
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className='glass-strong border-purple-muted/50 max-w-4xl max-h-[90vh] overflow-hidden'>
        <DialogHeader className='relative'>
          <div className='absolute -top-2 -right-2 w-16 h-16 bg-gradient-to-bl from-purple/10 to-transparent rounded-full' />
          <DialogTitle className='flex items-center space-x-3 text-xl'>
            <div className='p-2 bg-gradient-to-br from-purple/20 to-cyan/20 rounded-xl'>
              <VideoIcon className='w-6 h-6 text-white' />
            </div>
            <span className='text-white'>{cameraName} - Timelapses</span>
          </DialogTitle>
        </DialogHeader>

        <div className='mt-6 space-y-6 max-h-[calc(90vh-120px)] overflow-auto'>
          {loading ? (
            <div className='flex items-center justify-center py-12'>
              <div className='text-center space-y-4'>
                <div className='w-12 h-12 border-4 border-purple/20 border-t-purple rounded-full animate-spin mx-auto' />
                <p className='text-grey-light/60'>Loading timelapses...</p>
              </div>
            </div>
          ) : videos.length === 0 ? (
            <div className='text-center py-12'>
              <div className='w-20 h-20 bg-gradient-to-br from-purple/20 to-cyan/20 rounded-2xl flex items-center justify-center mx-auto mb-6'>
                <VideoIcon className='w-10 h-10 text-white/60' />
              </div>
              <h3 className='text-xl font-bold text-white mb-2'>
                No timelapses yet
              </h3>
              <p className='text-grey-light/60'>
                Timelapses will appear here once they're generated from captured
                images.
              </p>
            </div>
          ) : (
            <>
              {/* Video Player Section */}
              {selectedVideo && (
                <div className='space-y-4'>
                  <div className='aspect-video rounded-xl overflow-hidden bg-black border border-purple-muted/30'>
                    <video
                      key={selectedVideo.id}
                      controls
                      className='w-full h-full'
                    >
                      <source
                        src={`/api/videos/${selectedVideo.id}/download`}
                        type='video/mp4'
                      />
                      Your browser does not support the video tag.
                    </video>
                  </div>

                  {/* Selected Video Info */}
                  <div className='glass p-4 rounded-xl border border-purple-muted/20'>
                    <div className='flex items-center justify-between'>
                      <div className='space-y-2'>
                        <h4 className='font-bold text-white text-lg'>
                          {getVideoDisplayName(selectedVideo)}
                        </h4>
                        <div className='flex items-center space-x-4 text-sm text-grey-light/70'>
                          <div className='flex items-center space-x-1'>
                            <Calendar className='w-4 h-4' />
                            <span>
                              {formatDate(selectedVideo.created_at, timezone)}
                            </span>
                          </div>
                          <div className='flex items-center space-x-1'>
                            <Clock className='w-4 h-4' />
                            <span>
                              {formatDuration(selectedVideo.duration_seconds)}
                            </span>
                          </div>
                          <div className='flex items-center space-x-1'>
                            <HardDrive className='w-4 h-4' />
                            <span>
                              {formatFileSize(selectedVideo.file_size)}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className='flex items-center space-x-2'>
                        <Button
                          onClick={() => handleStartEdit(selectedVideo)}
                          size='sm'
                          variant='outline'
                          className='border-purple-muted/40 hover:bg-purple/20 text-white'
                        >
                          <Edit3 className='w-4 h-4 mr-1' />
                          Rename
                        </Button>
                        <Button
                          onClick={() => handleDownload(selectedVideo)}
                          size='sm'
                          className='bg-gradient-to-r from-cyan to-purple hover:from-cyan-dark hover:to-purple-dark text-black font-medium'
                        >
                          <Download className='w-4 h-4 mr-1' />
                          Download
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Video List */}
              <div className='space-y-3'>
                <h3 className='text-lg font-bold text-white flex items-center space-x-2'>
                  <VideoIcon className='w-5 h-5 text-purple-light' />
                  <span>All Timelapses ({videos.length})</span>
                </h3>

                <div className='space-y-2 max-h-64 overflow-y-auto'>
                  {videos.map((video) => (
                    <div
                      key={video.id}
                      className={cn(
                        "p-4 rounded-xl border cursor-pointer transition-all duration-200",
                        selectedVideo?.id === video.id
                          ? "glass-strong border-purple/50 bg-purple/10"
                          : "glass border-purple-muted/30 hover:border-purple-muted/50 hover:bg-purple/5"
                      )}
                      onClick={() => setSelectedVideo(video)}
                    >
                      <div className='flex items-center justify-between'>
                        <div className='flex items-center space-x-3'>
                          <div
                            className={cn(
                              "w-2 h-2 rounded-full",
                              selectedVideo?.id === video.id
                                ? "bg-purple"
                                : "bg-grey-light/30"
                            )}
                          />

                          <div className='space-y-1'>
                            {editingVideoId === video.id ? (
                              <div className='flex items-center space-x-2'>
                                <Input
                                  value={editName}
                                  onChange={(e) => setEditName(e.target.value)}
                                  className='h-8 bg-black/30 border-purple-muted/30 text-white text-sm'
                                  placeholder='Video name'
                                  autoFocus
                                />
                                <Button
                                  onClick={() => handleSaveEdit(video.id)}
                                  size='sm'
                                  className='h-8 w-8 p-0 bg-success/20 hover:bg-success/30 text-success'
                                >
                                  <Check className='w-4 h-4' />
                                </Button>
                                <Button
                                  onClick={handleCancelEdit}
                                  size='sm'
                                  className='h-8 w-8 p-0 bg-failure/20 hover:bg-failure/30 text-failure'
                                >
                                  <X className='w-4 h-4' />
                                </Button>
                              </div>
                            ) : (
                              <h4 className='font-medium text-white'>
                                {getVideoDisplayName(video)}
                              </h4>
                            )}

                            <div className='flex items-center space-x-3 text-xs text-grey-light/60'>
                              <span>
                                {formatDate(video.created_at, timezone)}
                              </span>
                              <span>•</span>
                              <span>
                                {formatDuration(video.duration_seconds)}
                              </span>
                              <span>•</span>
                              <span>{formatFileSize(video.file_size)}</span>
                            </div>
                          </div>
                        </div>

                        <div className='flex items-center space-x-2'>
                          {selectedVideo?.id === video.id && (
                            <div className='text-xs text-purple-light font-medium bg-purple/20 px-2 py-1 rounded-full'>
                              Now Playing
                            </div>
                          )}

                          <Button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleDownload(video)
                            }}
                            size='sm'
                            variant='ghost'
                            className='h-8 w-8 p-0 hover:bg-cyan/20 text-cyan/70 hover:text-cyan'
                          >
                            <Download className='w-4 h-4' />
                          </Button>

                          <Button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleStartEdit(video)
                            }}
                            size='sm'
                            variant='ghost'
                            className='h-8 w-8 p-0 hover:bg-purple/20 text-purple-light/70 hover:text-purple-light'
                          >
                            <Edit3 className='w-4 h-4' />
                          </Button>

                          <Button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleDelete(video)
                            }}
                            size='sm'
                            variant='ghost'
                            className='h-8 w-8 p-0 hover:bg-failure/20 text-failure/70 hover:text-failure'
                          >
                            <Trash2 className='w-4 h-4' />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </DialogContent>

      {/* Confirmation Dialog */}
      <DeleteTimelapseConfirmationDialog
        isOpen={confirmDeleteOpen}
        onClose={() => {
          setConfirmDeleteOpen(false)
          setVideoToDelete(null)
        }}
        onConfirm={confirmDeleteVideo}
        timelapseVideoName={
          videoToDelete ? getVideoDisplayName(videoToDelete) : "Unknown Video"
        }
        isLoading={deleteLoading}
      />
    </Dialog>
  )
}
