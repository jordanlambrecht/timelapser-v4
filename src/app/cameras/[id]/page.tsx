// src/app/cameras/[id]/page.tsx
"use client"

import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import {
  useRelativeTime,
  useCameraCountdown,
} from "@/hooks/use-camera-countdown"
import { useTimezoneSettings } from "@/contexts/settings-context"
import { useCameraDetails } from "@/hooks/use-camera-details"
import { useCameraSSE } from "@/hooks/use-camera-sse"
import { formatAbsoluteTime, formatRelativeTime } from "@/lib/time-utils"
import { toast } from "@/lib/toast"
import { TimelapseSettingsModal } from "@/components/ui/timelapse-settings-modal"
import { TimelapseDetailsModal } from "@/components/timelapse-details-modal"
import { CreateTimelapseDialog } from "@/components/create-timelapse-dialog"
import { CameraDetailsImage } from "@/components/camera-image-unified"
import { useLatestImageDetails } from "@/hooks/use-latest-image"
import { downloadLatestImage } from "@/lib/latest-image-api"
import { AnimatedGradientButton } from "@/components/ui/animated-gradient-button"
// import { AnimatedCountdownBorder } from "@/components/animated-countdown-border"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import {
  ArrowLeft,
  Camera,
  Video,
  Clock,
  Zap,
  Play,
  Square,
  Settings,
  Eye,
  CircleStop,
  Pause,
  Film,
  Download,
  ChevronRight,
  PlayCircle,
} from "lucide-react"
import cn from "clsx"
import Image from "next/image"

import { type TimelapseConfig } from "@/types"

export default function CameraDetailsPage() {
  const params = useParams()
  const router = useRouter()
  const cameraId = parseInt(params.id as string)

  // 🎯 REFACTORED: Single hook replaces 6 separate API calls
  const {
    camera,
    activeTimelapse,
    timelapses,
    videos,
    recentImages,
    recentActivity,
    stats,
    loading,
    error,
    refetch,
  } = useCameraDetails(cameraId)

  // Get timezone from settings
  const { timezone } = useTimezoneSettings()

  // UI state only - no more complex data management
  const [imageKey, setImageKey] = useState(Date.now()) // Force image refresh
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [showLatestCapture, setShowLatestCapture] = useState(true) // true = latest capture, false = latest timelapse video

  // Modal states
  const [selectedTimelapse, setSelectedTimelapse] = useState<any>(null)
  const [timelapseModalOpen, setTimelapseModalOpen] = useState(false)
  const [newTimelapseDialogOpen, setNewTimelapseDialogOpen] = useState(false)
  const [confirmStopOpen, setConfirmStopOpen] = useState(false)
  const [settingsModalOpen, setSettingsModalOpen] = useState(false)

  // Computed values from clean data
  const completedTimelapses = timelapses.filter((t) => t.status === "completed")
  const completedVideos = videos.filter((v) => v.status === "completed")

  // Timelapse status helpers
  const isTimelapseRunning = activeTimelapse?.status === "running"
  const isTimelapsePaused = activeTimelapse?.status === "paused"

  // Use the new time formatting hooks
  const lastImageCapturedText = useRelativeTime(
    camera?.last_image?.captured_at,
    {
      includeAbsolute: false,
      refreshInterval: 30000,
    }
  )

  // Countdown hook for next capture timing
  const countdownState = useCameraCountdown({
    camera: camera
      ? {
          id: camera.id,
          last_capture_at: camera.last_capture_at,
          next_capture_at:
            camera.last_image?.captured_at || camera.last_capture_at,
          time_window_start: camera.time_window_start,
          time_window_end: camera.time_window_end,
          use_time_window: camera.use_time_window,
        }
      : {
          id: 0,
          last_capture_at: null,
          next_capture_at: null,
          time_window_start: null,
          time_window_end: null,
          use_time_window: false,
        },
    timelapse: activeTimelapse || undefined,
    captureInterval: 300, // TODO: Get from active timelapse when backend supports per-timelapse intervals
    enabled: isTimelapseRunning,
  })

  // Extract progress for the animated border
  const { captureProgress } = countdownState

  // 🎯 REAL-TIME: SSE event handling for live updates (no React Query interference)
  useCameraSSE(cameraId, {
    onImageCaptured: () => {
      // Force image refresh with cache-busting - SSE system handles data updates
      setImageKey(Date.now())
      // Let useCameraDetails hook handle data refetching automatically
      refetch()
    },
    onStatusChanged: () => {
      // Force image refresh and let SSE system handle data updates
      setImageKey(Date.now())
      refetch()
    },
    onTimelapseStatusChanged: () => {
      // Force image refresh and let SSE system handle data updates
      setImageKey(Date.now())
      refetch()
    },
    onTimelapseStarted: (data) => {
      console.log("🎬 Timelapse started via SSE:", data)
      toast.timelapseStarted(camera?.name || "Camera")
      setNewTimelapseDialogOpen(false)
      setImageKey(Date.now())
      refetch()
    },
    onTimelapsePaused: (data) => {
      console.log("⏸️ Timelapse paused via SSE:", data)
      toast.timelapsePaused(camera?.name || "Camera")
      refetch()
    },
    onTimelapseResumed: (data) => {
      console.log("▶️ Timelapse resumed via SSE:", data)
      toast.timelapseResumed(camera?.name || "Camera")
      refetch()
    },
    onTimelapseStopped: (data) => {
      console.log("⏹️ Timelapse stopped via SSE:", data)
      toast.success(`⏹️ Timelapse stopped for ${camera?.name || "Camera"}`, {
        description: "Recording session has ended",
      })
      setImageKey(Date.now())
      refetch()
    },
    onTimelapseCompleted: (data) => {
      console.log("✅ Timelapse completed via SSE:", data)
      toast.success(`✅ Timelapse completed for ${camera?.name || "Camera"}`, {
        description: "Recording session archived",
      })
      setImageKey(Date.now())
      refetch()
    },
    onCameraUpdated: () => {
      // Force image refresh and let SSE system handle data updates
      setImageKey(Date.now())
      refetch()
    },
  })

  // 🎯 REMOVED: fetchAllCameraData function - replaced by useCameraDetails hook

  // 🎯 REMOVED: fetchTimelapseImages function - using comprehensive hook for data

  const handlePauseTimelapse = async () => {
    if (!camera || !activeTimelapse) return

    try {
      setActionLoading("pause")

      const response = await fetch(
        `/api/cameras/${camera.id}/pause-timelapse`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        }
      )

      if (response.ok) {
        // SSE event will handle state update automatically - no manual refetch needed
        // toast.timelapsePaused(camera.name) // Removed - SSE handler shows toast
      } else {
        throw new Error("Failed to pause timelapse")
      }
    } catch (error) {
      console.error("Error pausing timelapse:", error)
      toast.error("Failed to pause timelapse", {
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
      })
    } finally {
      setActionLoading(null)
    }
  }

  const handleResumeTimelapse = async () => {
    if (!camera || !activeTimelapse) return

    try {
      setActionLoading("resume")

      const response = await fetch(
        `/api/cameras/${camera.id}/resume-timelapse`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        }
      )

      if (response.ok) {
        // SSE event will handle state update automatically - no manual refetch needed
        // toast.timelapseResumed(camera.name) // Removed - SSE handler shows toast
      } else {
        throw new Error("Failed to resume timelapse")
      }
    } catch (error) {
      console.error("Error resuming timelapse:", error)
      toast.error("Failed to resume timelapse", {
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
      })
    } finally {
      setActionLoading(null)
    }
  }

  const handleStopTimelapse = async () => {
    if (!camera || !activeTimelapse) return

    try {
      setActionLoading("stop")

      // Complete the timelapse using camera-centric endpoint
      const response = await fetch(`/api/cameras/${camera.id}/stop-timelapse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      })

      if (response.ok) {
        // SSE event will handle state update automatically - no manual refetch needed
        // Toast and image refresh handled by SSE event handler
      } else {
        throw new Error("Failed to stop timelapse")
      }
    } catch (error) {
      console.error("Error stopping timelapse:", error)
      toast.error("Failed to stop timelapse", {
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
      })
    } finally {
      setActionLoading(null)
    }
  }

  const handleStartNewTimelapse = async (config: TimelapseConfig) => {
    if (!camera) return

    try {
      setActionLoading("start")

      // ARCHITECTURAL LAW: Timezone-aware validation for auto-stop
      if (config.useAutoStop && config.autoStopAt) {
        const autoStopDate = new Date(config.autoStopAt)
        const now = new Date()
        if (autoStopDate <= now) {
          toast.error("Auto-stop time must be in the future")
          throw new Error("Invalid auto-stop time")
        }
      }

      // Send minimal data - let backend apply defaults via Pydantic model
      const timelapseData: any = {
        name: config.name,
      }

      // Only include optional fields if they differ from defaults
      if (config.useAutoStop && config.autoStopAt) {
        timelapseData.auto_stop_at = config.autoStopAt
      }

      if (config.timeWindowType === "time") {
        timelapseData.time_window_type = "time"
        timelapseData.time_window_start = config.timeWindowStart
        timelapseData.time_window_end = config.timeWindowEnd
        timelapseData.use_custom_time_window = true
      } else if (config.timeWindowType === "sunrise_sunset") {
        timelapseData.time_window_type = "sunrise_sunset"
        timelapseData.use_custom_time_window = true
      }

      // Include video settings if provided
      if (config.videoSettings) {
        Object.assign(timelapseData, config.videoSettings)
      }

      // No optimistic updates needed - comprehensive hook will handle data updates

      // Use the camera-centric start timelapse endpoint
      const response = await fetch(
        `/api/cameras/${camera.id}/start-timelapse`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(timelapseData),
        }
      )

      const result = await response.json()

      if (response.ok) {
        toast.timelapseStarted(camera.name)
        setNewTimelapseDialogOpen(false)
        // SSE event will handle all state updates automatically
        // Force image refresh with cache-busting
        setImageKey(Date.now())
      } else {
        // On failure, refetch to get fresh state
        refetch()
        throw new Error(result.detail || "Failed to start timelapse")
      }
    } catch (error) {
      console.error("Error starting new timelapse:", error)
      toast.error("Failed to start timelapse", {
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        duration: 6000,
      })
      throw error // Re-throw so dialog handles loading state properly
    } finally {
      setActionLoading(null)
    }
  }

  // 🎯 REMOVED: handleDeleteImages function - referenced undefined selectedVideo variable
  // This function was never called from the UI and contained references to undefined variables.
  // Image management functionality should be implemented with proper state management when needed.

  // 🎯 REMOVED: handleRegenerateVideo function - no longer called after removing handleDeleteImages
  // Video regeneration functionality should be implemented through the main video management UI when needed.

  // Helper functions
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes"
    const k = 1024
    const sizes = ["Bytes", "KB", "MB", "GB"]
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
  }

  const formatDuration = (seconds: number) => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, "0")}:${secs
        .toString()
        .padStart(2, "0")}`
    }
    return `${minutes}:${secs.toString().padStart(2, "0")}`
  }

  const getHealthStatusIcon = (status: string) => {
    switch (status) {
      case "healthy":
        return "🟢"
      case "warning":
        return "🟡"
      case "error":
        return "🔴"
      default:
        return "⚪"
    }
  }

  const getHealthStatusColor = (status: string) => {
    switch (status) {
      case "healthy":
        return "bg-green-100 text-green-600"
      case "warning":
        return "bg-yellow-100 text-yellow-600"
      case "error":
        return "bg-red-100 text-red-600"
      default:
        return "bg-gray-100 text-primary"
    }
  }

  // 🎯 REMOVED: Dead code for image filtering/sorting
  // This code referenced undefined variables (imageSearchTerm, imageSortBy, imageSortOrder)
  // and was never used in the actual UI. The comprehensive hook provides recentImages
  // for display purposes, but full image management is handled elsewhere.

  if (loading) {
    return (
      <div className='flex items-center justify-center min-h-screen glass'>
        <div className='text-center'>
          <div className='w-12 h-12 mx-auto border-b-2 border-blue-600 rounded-full animate-spin'></div>
          <p className='mt-4 text-primary'>Loading camera details...</p>
        </div>
      </div>
    )
  }

  if (error || !camera) {
    return (
      <div className='flex items-center justify-center min-h-screen glass'>
        <div className='text-center'>
          <p className='mb-4 text-lg text-failure'>
            {error || "Camera not found"}
          </p>
          <Link href='/' className='text-blue-600 hover:text-blue-800'>
            ← Back to Dashboard
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className='min-h-screen glass'>
      {/* Header */}
      <div className='glass-strong shadow-sm'>
        <div className='px-4 py-4 mx-auto max-w-7xl sm:px-6 lg:px-8'>
          <div className='flex items-center justify-between'>
            <div className='flex items-center gap-4'>
              <Link
                href='/'
                className='text-blue-600 hover:text-blue-800 transition-colors'
              >
                <ArrowLeft className='w-5 h-5' />
              </Link>
              <div className='flex items-center gap-3'>
                <div className='p-2 glass rounded-lg'>
                  <Camera className='w-5 h-5 text-accent' />
                </div>
                <div>
                  <h1 className='text-2xl font-bold text-white'>
                    {camera.name}
                  </h1>
                  <p className='text-sm text-primary'>Camera #{camera.id}</p>
                </div>
              </div>
              <div className='flex items-center gap-3'>
                {/* Online status indicator with dot */}
                <div className='flex items-center gap-2'>
                  <div
                    className={cn(
                      "w-3 h-3 rounded-full border-2 border-white/50 transition-all duration-300",
                      camera.health_status === "online"
                        ? "bg-green-500 shadow-lg shadow-green-500/50 animate-pulse"
                        : camera.health_status === "offline"
                        ? "bg-red-500 shadow-lg shadow-red-500/50 animate-pulse"
                        : "bg-yellow-500 shadow-lg shadow-yellow-500/50 animate-pulse"
                    )}
                  />
                  <span
                    className={`px-3 py-1 text-xs rounded-full font-medium ${getHealthStatusColor(
                      camera.health_status
                    )}`}
                  >
                    {camera.health_status}
                  </span>
                </div>

                {/* Recording Status Badge */}
                {stats?.current_timelapse_status === "running" && (
                  <div className='flex items-center gap-2'>
                    <div className='w-2 h-2 bg-cyan rounded-full animate-pulse' />
                    <span className='px-3 py-1 text-xs rounded-full font-medium bg-gradient-to-r from-cyan/10 to-purple/10 text-cyan border border-cyan/20'>
                      Recording:{" "}
                      {stats.current_timelapse_name || "Unnamed Timelapse"}
                    </span>
                  </div>
                )}

                {/* Settings Button */}
                <Button
                  onClick={() => setSettingsModalOpen(true)}
                  size='sm'
                  variant='outline'
                  className='border-purple-muted/40 hover:bg-purple/20 text-white'
                  title='Camera Settings'
                >
                  <Settings className='w-4 h-4' />
                </Button>
              </div>
            </div>

            {/* Main Control Button */}
            <div className='flex items-center gap-3'>
              {isTimelapseRunning && (
                <Button
                  onClick={handlePauseTimelapse}
                  disabled={actionLoading === "pause"}
                  size='sm'
                  className='bg-yellow-600 hover:bg-yellow-700 text-white'
                >
                  {actionLoading === "pause" ? (
                    <>
                      <div className='w-4 h-4 mr-2 border-2 border-white border-t-transparent rounded-full animate-spin' />
                      Pausing...
                    </>
                  ) : (
                    <>
                      <Pause className='w-4 h-4 mr-2' />
                      Pause
                    </>
                  )}
                </Button>
              )}

              {isTimelapsePaused && (
                <Button
                  onClick={handleResumeTimelapse}
                  disabled={actionLoading === "resume"}
                  size='sm'
                  className='bg-green-600 hover:bg-green-700 text-white'
                >
                  {actionLoading === "resume" ? (
                    <>
                      <div className='w-4 h-4 mr-2 border-2 border-white border-t-transparent rounded-full animate-spin' />
                      Resuming...
                    </>
                  ) : (
                    <>
                      <Play className='w-4 h-4 mr-2' />
                      Resume
                    </>
                  )}
                </Button>
              )}

              {camera.health_status === "offline" ? (
                <Button
                  onClick={() => {}}
                  size='lg'
                  disabled={true}
                  className='bg-gray-600 text-gray-400 cursor-not-allowed opacity-50 font-medium transition-all duration-300 min-w-[160px]'
                >
                  <Square className='w-4 h-4 mr-2' />
                  Offline
                </Button>
              ) : isTimelapseRunning || isTimelapsePaused ? (
                <Button
                  onClick={() => setConfirmStopOpen(true)}
                  size='lg'
                  className='bg-failure/80 hover:bg-failure text-white hover:shadow-lg hover:shadow-failure/20 font-medium transition-all duration-300 min-w-[160px]'
                >
                  <CircleStop className='w-4 h-4 mr-2' />
                  Stop Timelapse
                </Button>
              ) : (
                <AnimatedGradientButton
                  onClick={() => setNewTimelapseDialogOpen(true)}
                  size='lg'
                  className='font-medium min-w-[160px]'
                >
                  <Play className='w-4 h-4 mr-2' />
                  Start New Timelapse
                </AnimatedGradientButton>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className='px-4 py-8 mx-auto max-w-7xl sm:px-6 lg:px-8'>
        <div className='grid grid-cols-1 gap-8 lg:grid-cols-4'>
          {/* Main Content */}
          <div className='lg:col-span-3 space-y-8'>
            {/* Latest Image */}
            <div className='glass-strong rounded-2xl shadow-xl overflow-hidden'>
              <div className='p-6'>
                <div className='flex items-center justify-between mb-6'>
                  <div className='flex items-center gap-4'>
                    <h2 className='text-xl font-bold text-white flex items-center gap-2'>
                      <Eye className='w-5 h-5 text-accent' />
                      {showLatestCapture
                        ? "Latest Capture"
                        : "Latest Timelapse Video"}
                    </h2>

                    {/* Toggle between latest capture and latest timelapse */}
                    <div className='flex items-center space-x-2'>
                      <Button
                        onClick={() => setShowLatestCapture(true)}
                        size='sm'
                        variant={showLatestCapture ? "default" : "outline"}
                        className={`transition-all duration-300 ${
                          showLatestCapture
                            ? "bg-cyan text-black shadow-lg shadow-cyan/20"
                            : "border-gray-600 text-gray-400 hover:text-white hover:border-gray-400"
                        }`}
                      >
                        <Camera className='w-4 h-4 mr-1' />
                        Image
                      </Button>
                      <Button
                        onClick={() => setShowLatestCapture(false)}
                        size='sm'
                        variant={!showLatestCapture ? "default" : "outline"}
                        className={`transition-all duration-300 ${
                          !showLatestCapture
                            ? "bg-purple text-white shadow-lg shadow-purple/20"
                            : "border-gray-600 text-gray-400 hover:text-white hover:border-gray-400"
                        }`}
                        disabled={completedVideos.length === 0}
                      >
                        <Video className='w-4 h-4 mr-1' />
                        Video
                      </Button>
                    </div>
                  </div>

                  {showLatestCapture && camera.last_image && (
                    <div className='flex flex-col items-end gap-1 text-sm'>
                      <div className='flex items-center gap-2 text-primary'>
                        <Clock className='w-4 h-4' />
                        {lastImageCapturedText}
                      </div>
                      <div className='text-xs text-yellow-400 font-mono'>
                        {formatAbsoluteTime(
                          camera.last_image.captured_at,
                          timezone
                        )}
                      </div>
                    </div>
                  )}
                </div>

                <div className='glass-strong rounded-xl aspect-video overflow-hidden transition-all duration-500 relative group'>
                  {showLatestCapture ? (
                    // Latest Image View
                    camera.last_image ? (
                      <>
                        <CameraDetailsImage
                          cameraId={camera.id}
                          cameraName={camera.name}
                          className='object-cover w-full h-full hover:scale-105 transition-transform duration-300'
                        />
                        {/* Download Button for Image */}
                        <Button
                          onClick={async () => {
                            try {
                              await downloadLatestImage(camera.id)
                              toast.success("Image downloaded successfully!")
                            } catch (error) {
                              console.error("Error downloading image:", error)
                              toast.error("Failed to download image")
                            }
                          }}
                          size='sm'
                          className='absolute bottom-3 right-3 bg-black/60 hover:bg-black/80 text-white border border-white/20 backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-all duration-300 shadow-lg'
                          title='Download latest capture'
                        >
                          <Download className='w-4 h-4' />
                        </Button>

                        {/* Capture Progress Indicator */}
                        {isTimelapseRunning && captureProgress > 0 && (
                          <div className='absolute top-3 left-3 bg-black/60 hover:bg-black/80 text-white border border-yellow-400/30 backdrop-blur-sm px-3 py-1 rounded-md text-sm font-medium transition-all duration-300'>
                            <div className='flex items-center gap-2'>
                              <div className='w-2 h-2 bg-yellow-400 rounded-full animate-pulse' />
                              {Math.round(captureProgress)}% to next capture
                            </div>
                          </div>
                        )}
                      </>
                    ) : (
                      <div className='flex items-center justify-center w-full h-full text-gray-500'>
                        <div className='text-center'>
                          <Camera className='w-16 h-16 mx-auto text-gray-400 mb-4' />
                          <p className='text-lg font-medium'>
                            No images captured yet
                          </p>
                          <p className='text-sm mt-2'>
                            Start a timelapse to begin capturing
                          </p>
                        </div>
                      </div>
                    )
                  ) : // Latest Video View
                  completedVideos.length > 0 ? (
                    <div className='relative w-full h-full bg-black'>
                      <video
                        controls
                        className='w-full h-full object-contain'
                        poster={`/api/cameras/${camera.id}/latest-image/small`}
                      >
                        <source
                          src={`/api/videos/${completedVideos[0].id}/stream`}
                          type='video/mp4'
                        />
                        Your browser does not support the video tag.
                      </video>
                      <div className='absolute top-3 left-3 bg-black/50 backdrop-blur-sm rounded-lg px-3 py-2'>
                        <p className='text-sm text-white font-medium'>
                          {completedVideos[0].file_path?.split("/").pop() ||
                            "Latest Video"}
                        </p>
                        <p className='text-xs text-gray-300'>
                          {completedVideos[0].duration_seconds
                            ? `${Math.floor(
                                completedVideos[0].duration_seconds / 60
                              )}:${String(
                                completedVideos[0].duration_seconds % 60
                              ).padStart(2, "0")}`
                            : "Unknown duration"}
                        </p>
                      </div>
                      {/* Download Button for Video */}
                      <Button
                        onClick={async () => {
                          try {
                            const response = await fetch(
                              `/api/videos/${completedVideos[0].id}/download`
                            )
                            if (!response.ok) {
                              throw new Error("Failed to download video")
                            }
                            const blob = await response.blob()
                            const url = window.URL.createObjectURL(blob)
                            const a = document.createElement("a")
                            a.href = url
                            a.download =
                              completedVideos[0].file_path?.split("/").pop() ||
                              `${camera.name}_latest_video.mp4`
                            document.body.appendChild(a)
                            a.click()
                            document.body.removeChild(a)
                            window.URL.revokeObjectURL(url)
                            toast.success("Video downloaded successfully!")
                          } catch (error) {
                            console.error("Error downloading video:", error)
                            toast.error("Failed to download video")
                          }
                        }}
                        size='sm'
                        className='absolute bottom-3 right-3 bg-black/60 hover:bg-black/80 text-white border border-white/20 backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-all duration-300 shadow-lg'
                        title='Download latest video'
                      >
                        <Download className='w-4 h-4' />
                      </Button>
                    </div>
                  ) : (
                    <div className='flex items-center justify-center w-full h-full text-gray-500'>
                      <div className='text-center'>
                        <Video className='w-16 h-16 mx-auto text-gray-400 mb-4' />
                        <p className='text-lg font-medium'>
                          No timelapse videos yet
                        </p>
                        <p className='text-sm mt-2'>
                          Generate your first video from captured images
                        </p>
                      </div>
                    </div>
                  )}
                </div>

                {showLatestCapture
                  ? // Image stats
                    camera.last_image && (
                      <div className='grid grid-cols-2 md:grid-cols-5 gap-4 mt-6 text-sm'>
                        <div className='glass rounded-lg p-3'>
                          <div className='text-primary font-medium'>
                            Captured
                          </div>
                          <div className='text-white'>
                            {lastImageCapturedText}
                          </div>
                          <div className='text-xs text-yellow-400 font-mono mt-1'>
                            {formatAbsoluteTime(
                              camera.last_image.captured_at,
                              timezone
                            )}
                          </div>
                        </div>
                        <div className='glass rounded-lg p-3'>
                          <div className='text-primary font-medium'>
                            Resolution
                          </div>
                          <div className='text-white'>2688×1512</div>
                          <div className='text-xs text-gray-400'>4MP</div>
                        </div>
                        <div className='glass rounded-lg p-3'>
                          <div className='text-primary font-medium'>Day</div>
                          <div className='text-white'>
                            #{camera.last_image.day_number}
                          </div>
                        </div>
                        <div className='glass rounded-lg p-3'>
                          <div className='text-primary font-medium'>
                            File Size
                          </div>
                          <div className='text-white'>
                            {formatFileSize(camera.last_image.file_size || 0)}
                          </div>
                        </div>
                        <div className='glass rounded-lg p-3'>
                          <div className='text-primary font-medium'>
                            Timelapse
                          </div>
                          <div className='text-white'>
                            {activeTimelapse
                              ? `#${activeTimelapse.id}`
                              : "None"}
                          </div>
                        </div>
                      </div>
                    )
                  : // Video stats
                    completedVideos.length > 0 && (
                      <div className='grid grid-cols-2 md:grid-cols-5 gap-4 mt-6 text-sm'>
                        <div className='glass rounded-lg p-3'>
                          <div className='text-primary font-medium'>
                            Created
                          </div>
                          <div className='text-white'>
                            {formatRelativeTime(completedVideos[0].created_at, {
                              timezone,
                            })}
                          </div>
                          <div className='text-xs text-yellow-400 font-mono mt-1'>
                            {formatAbsoluteTime(
                              completedVideos[0].created_at,
                              timezone
                            )}
                          </div>
                        </div>
                        <div className='glass rounded-lg p-3'>
                          <div className='text-primary font-medium'>
                            Duration
                          </div>
                          <div className='text-white'>
                            {completedVideos[0].duration_seconds
                              ? `${Math.floor(
                                  completedVideos[0].duration_seconds / 60
                                )}:${String(
                                  completedVideos[0].duration_seconds % 60
                                ).padStart(2, "0")}`
                              : "Unknown"}
                          </div>
                          <div className='text-xs text-gray-400'>mm:ss</div>
                        </div>
                        <div className='glass rounded-lg p-3'>
                          <div className='text-primary font-medium'>
                            File Size
                          </div>
                          <div className='text-white'>
                            {formatFileSize(completedVideos[0].file_size || 0)}
                          </div>
                        </div>
                        <div className='glass rounded-lg p-3'>
                          <div className='text-primary font-medium'>Images</div>
                          <div className='text-white'>
                            {completedVideos[0].settings?.total_images || "N/A"}
                          </div>
                          <div className='text-xs text-gray-400'>used</div>
                        </div>
                        <div className='glass rounded-lg p-3'>
                          <div className='text-primary font-medium'>FPS</div>
                          <div className='text-white'>
                            {completedVideos[0].settings?.fps || "N/A"}
                          </div>
                          <div className='text-xs text-gray-400'>
                            frames/sec
                          </div>
                        </div>
                      </div>
                    )}
              </div>
            </div>

            {/* Timelapses Table */}
            <div className='glass-strong rounded-2xl shadow-xl overflow-hidden'>
              <div className='p-6'>
                <div className='flex items-center justify-between mb-6'>
                  <h2 className='text-xl font-bold text-white flex items-center gap-2'>
                    <Film className='w-5 h-5 text-accent' />
                    Timelapses
                  </h2>
                  <div className='flex items-center gap-2 text-sm text-primary'>
                    <span>{timelapses.length} total</span>
                    {completedTimelapses.length > 0 && (
                      <span>• {completedTimelapses.length} completed</span>
                    )}
                  </div>
                </div>

                {timelapses.length > 0 ? (
                  <div className='overflow-hidden rounded-lg'>
                    <div className='overflow-x-auto'>
                      <table className='w-full'>
                        <thead>
                          <tr className='border-b border-gray-700'>
                            <th className='text-left py-3 px-4 font-medium text-primary'>
                              Name
                            </th>
                            <th className='text-left py-3 px-4 font-medium text-primary'>
                              Status
                            </th>
                            <th className='text-left py-3 px-4 font-medium text-primary'>
                              Images
                            </th>
                            <th className='text-left py-3 px-4 font-medium text-primary'>
                              Started
                            </th>
                            <th className='text-left py-3 px-4 font-medium text-primary'>
                              Last Capture
                            </th>
                            <th className='text-left py-3 px-4 font-medium text-primary'>
                              Actions
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {timelapses.map((timelapse) => (
                            <tr
                              key={timelapse.id}
                              className='border-b border-gray-800 hover:bg-gray-800/50 transition-colors cursor-pointer'
                              onClick={() => {
                                const numericId = parseInt(
                                  timelapse.id?.toString()
                                )
                                if (isNaN(numericId)) {
                                  toast.error("Invalid timelapse ID")
                                  return
                                }

                                setSelectedTimelapse({
                                  ...timelapse,
                                  id: numericId,
                                })
                                setTimelapseModalOpen(true)
                              }}
                            >
                              <td className='py-4 px-4'>
                                <div className='text-white font-medium'>
                                  {timelapse.name ||
                                    `Timelapse #${timelapse.id}`}
                                </div>
                              </td>
                              <td className='py-4 px-4'>
                                <span
                                  className={cn(
                                    "px-2 py-1 rounded-full text-xs font-medium",
                                    timelapse.status === "running" &&
                                      "bg-green-100 text-green-800",
                                    timelapse.status === "paused" &&
                                      "bg-yellow-100 text-yellow-800",
                                    timelapse.status === "completed" &&
                                      "bg-blue-100 text-blue-800",
                                    timelapse.status === "archived" &&
                                      "bg-gray-100 text-gray-800"
                                  )}
                                >
                                  {timelapse.status}
                                  {timelapse.status === "running" && (
                                    <span className='ml-1 inline-block w-2 h-2 bg-green-500 rounded-full animate-pulse' />
                                  )}
                                </span>
                              </td>
                              <td className='py-4 px-4 text-white'>
                                {timelapse.image_count.toLocaleString()}
                              </td>
                              <td className='py-4 px-4 text-primary'>
                                {new Date(
                                  timelapse.start_date
                                ).toLocaleDateString("en-US", {
                                  timeZone: timezone,
                                  month: "short",
                                  day: "numeric",
                                  year: "numeric",
                                })}
                              </td>
                              <td className='py-4 px-4 text-primary'>
                                {timelapse.last_capture_at
                                  ? formatRelativeTime(
                                      timelapse.last_capture_at,
                                      { timezone }
                                    )
                                  : "Never"}
                              </td>
                              <td className='py-4 px-4'>
                                <div className='flex items-center gap-2'>
                                  <Button
                                    size='sm'
                                    variant='outline'
                                    className='text-accent border-accent hover:bg-accent hover:text-black'
                                    onClick={(e) => {
                                      e.stopPropagation()

                                      const numericId = parseInt(
                                        timelapse.id?.toString()
                                      )
                                      if (isNaN(numericId)) {
                                        toast.error("Invalid timelapse ID")
                                        return
                                      }

                                      setSelectedTimelapse({
                                        ...timelapse,
                                        id: numericId,
                                      })
                                      setTimelapseModalOpen(true)
                                    }}
                                  >
                                    <Eye className='w-4 h-4' />
                                  </Button>
                                  <ChevronRight className='w-4 h-4 text-gray-500' />
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : (
                  <div className='text-center py-12'>
                    <Film className='w-16 h-16 mx-auto text-gray-400 mb-4' />
                    <p className='text-lg font-medium text-gray-400'>
                      No timelapses yet
                    </p>
                    <p className='text-sm text-gray-500 mt-2'>
                      Start your first timelapse to begin capturing memories
                    </p>
                    <Button
                      onClick={() => setNewTimelapseDialogOpen(true)}
                      className='mt-4 bg-gradient-to-r from-pink to-cyan hover:from-pink-dark hover:to-cyan text-black'
                    >
                      <Play className='w-4 h-4 mr-2' />
                      Start New Timelapse
                    </Button>
                  </div>
                )}
              </div>
            </div>

            {/* Recent Activity */}
            <div className='glass-strong rounded-2xl shadow-xl overflow-hidden'>
              <div className='p-6'>
                <h3 className='text-lg font-bold text-white mb-6 flex items-center gap-2'>
                  <Clock className='w-5 h-5 text-accent' />
                  Recent Activity
                </h3>
                <div className='space-y-3'>
                  {recentActivity.length > 0 ? (
                    recentActivity.map((log) => (
                      <div
                        key={log.id}
                        className='flex items-start gap-3 p-4 rounded-lg glass hover:bg-gray-800/50 transition-colors'
                      >
                        <div
                          className={cn(
                            "px-2 py-1 text-xs rounded font-medium",
                            log.level === "error"
                              ? "bg-red-100 text-red-800"
                              : log.level === "warning"
                              ? "bg-yellow-100 text-yellow-800"
                              : "bg-blue-100 text-blue-800"
                          )}
                        >
                          {log.level.toUpperCase()}
                        </div>
                        <div className='flex-1'>
                          <p className='text-sm text-white'>{log.message}</p>
                          <p className='mt-1 text-xs text-primary'>
                            {formatRelativeTime(log.timestamp, { timezone })}
                          </p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className='text-center py-8'>
                      <p className='text-gray-500'>No recent activity</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Sidebar - Stats and Controls */}
          <div className='space-y-6'>
            {/* Stats */}
            <div className='glass-strong rounded-2xl shadow-xl overflow-hidden'>
              <div className='p-6'>
                <h3 className='text-lg font-bold text-white mb-6 flex items-center gap-2'>
                  <Zap className='w-5 h-5 text-accent' />
                  Statistics
                </h3>
                <div className='space-y-4'>
                  <div className='glass rounded-lg p-4'>
                    <div className='flex justify-between items-center'>
                      <span className='text-primary font-medium'>
                        Current Timelapse
                      </span>
                      <span className='text-xl font-bold text-white'>
                        {stats?.current_timelapse_images?.toLocaleString() ||
                          "0"}
                      </span>
                    </div>
                    <div className='text-xs text-gray-500 mt-1'>
                      images captured
                    </div>
                  </div>

                  <div className='glass rounded-lg p-4'>
                    <div className='flex justify-between items-center'>
                      <span className='text-primary font-medium'>
                        Total Images
                      </span>
                      <span className='text-xl font-bold text-white'>
                        {stats?.total_images?.toLocaleString() || "0"}
                      </span>
                    </div>
                    <div className='text-xs text-gray-500 mt-1'>all time</div>
                  </div>

                  <div className='glass rounded-lg p-4'>
                    <div className='flex justify-between items-center'>
                      <span className='text-primary font-medium'>
                        Videos Generated
                      </span>
                      <span className='text-xl font-bold text-white'>
                        {stats?.total_videos || "0"}
                      </span>
                    </div>
                    <div className='text-xs text-gray-500 mt-1'>completed</div>
                  </div>

                  <div className='glass rounded-lg p-4'>
                    <div className='flex justify-between items-center'>
                      <span className='text-primary font-medium'>
                        Timelapses
                      </span>
                      <span className='text-xl font-bold text-white'>
                        {stats?.timelapse_count || "0"}
                      </span>
                    </div>
                    <div className='text-xs text-gray-500 mt-1'>created</div>
                  </div>

                  <div className='glass rounded-lg p-4'>
                    <div className='flex justify-between items-center'>
                      <span className='text-primary font-medium'>
                        Days Active
                      </span>
                      <span className='text-xl font-bold text-white'>
                        {stats?.days_since_first_capture || "0"}
                      </span>
                    </div>
                    <div className='text-xs text-gray-500 mt-1'>
                      since first capture
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Timelapse Status */}
            <div className='glass-strong rounded-2xl shadow-xl overflow-hidden'>
              <div className='p-6'>
                <h3 className='text-lg font-bold text-white mb-6 flex items-center gap-2'>
                  <PlayCircle className='w-5 h-5 text-accent' />
                  Timelapse Status
                </h3>
                {activeTimelapse ? (
                  <div className='space-y-4'>
                    {/* Timelapse Name */}
                    <div className='glass rounded-lg p-4'>
                      <div className='flex justify-between items-center mb-2'>
                        <span className='text-primary font-medium'>Name</span>
                        <span className='text-white font-medium'>
                          {stats?.current_timelapse_name ||
                            activeTimelapse.name ||
                            "Unnamed Timelapse"}
                        </span>
                      </div>
                      <div className='text-xs text-gray-500'>
                        Timelapse #{activeTimelapse.id}
                      </div>
                    </div>

                    <div className='glass rounded-lg p-4'>
                      <div className='flex justify-between items-center mb-2'>
                        <span className='text-primary font-medium'>Status</span>
                        <span
                          className={cn(
                            "px-3 py-1 text-xs rounded-full font-medium",
                            activeTimelapse.status === "running"
                              ? "bg-green-100 text-green-800"
                              : activeTimelapse.status === "paused"
                              ? "bg-yellow-100 text-yellow-800"
                              : "bg-gray-100 text-gray-800"
                          )}
                        >
                          {activeTimelapse.status}
                          {activeTimelapse.status === "running" && (
                            <span className='ml-1 inline-block w-2 h-2 bg-green-500 rounded-full animate-pulse' />
                          )}
                        </span>
                      </div>
                    </div>

                    <div className='glass rounded-lg p-4'>
                      <div className='flex justify-between items-center mb-2'>
                        <span className='text-primary font-medium'>
                          Started
                        </span>
                        <span className='text-white font-medium'>
                          {new Date(
                            activeTimelapse.start_date
                          ).toLocaleDateString("en-US", {
                            timeZone: timezone,
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })}
                        </span>
                      </div>
                      <div className='text-xs text-gray-500'>
                        {formatRelativeTime(activeTimelapse.start_date, {
                          timezone,
                        })}{" "}
                        ago
                      </div>
                    </div>

                    <div className='glass rounded-lg p-4'>
                      <div className='flex justify-between items-center mb-2'>
                        <span className='text-primary font-medium'>Images</span>
                        <span className='text-white font-bold text-lg'>
                          {(
                            stats?.current_timelapse_images ||
                            activeTimelapse.image_count ||
                            0
                          ).toLocaleString()}
                        </span>
                      </div>
                      <div className='text-xs text-gray-500'>
                        captured so far
                      </div>
                    </div>

                    {activeTimelapse.last_capture_at && (
                      <div className='glass rounded-lg p-4'>
                        <div className='flex justify-between items-center mb-2'>
                          <span className='text-primary font-medium'>
                            Last Capture
                          </span>
                          <span className='text-white font-medium'>
                            {formatRelativeTime(
                              activeTimelapse.last_capture_at,
                              { timezone }
                            )}
                          </span>
                        </div>
                        <div className='text-xs text-gray-500'>
                          {new Date(
                            activeTimelapse.last_capture_at
                          ).toLocaleString("en-US", {
                            timeZone: timezone,
                            month: "short",
                            day: "numeric",
                            hour: "numeric",
                            minute: "2-digit",
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className='text-center py-8'>
                    <PlayCircle className='w-12 h-12 mx-auto text-gray-400 mb-3' />
                    <p className='text-gray-400 font-medium'>
                      No active timelapse
                    </p>
                    <p className='text-gray-500 text-sm mt-1'>
                      Start one to begin capturing
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Capture Controls */}
            <div className='glass-strong rounded-2xl shadow-xl overflow-hidden'>
              <div className='p-6'>
                <h3 className='text-lg font-bold text-white mb-6 flex items-center gap-2'>
                  <Camera className='w-5 h-5 text-accent' />
                  Capture Controls
                </h3>

                {/* Next Capture Countdown */}
                <div className='space-y-4'>
                  <div className='glass rounded-lg p-4'>
                    <div className='flex justify-between items-center mb-2'>
                      <span className='text-primary font-medium'>
                        Next Capture
                      </span>
                      <span
                        className={`font-mono text-lg ${
                          isTimelapseRunning
                            ? countdownState.isOverdue
                              ? "text-red-400"
                              : countdownState.isNow
                              ? "text-green-400"
                              : "text-white"
                            : "text-gray-400"
                        }`}
                      >
                        {isTimelapseRunning
                          ? countdownState.countdown
                          : "Inactive"}
                      </span>
                    </div>
                    <div className='text-xs text-gray-500 mt-1'>
                      {isTimelapseRunning
                        ? countdownState.isOverdue
                          ? "capture overdue"
                          : countdownState.isNow
                          ? "capturing now"
                          : "countdown timer"
                        : "no active timelapse"}
                    </div>
                    {isTimelapseRunning &&
                      countdownState.nextCaptureAbsolute && (
                        <div className='text-xs text-yellow-400 font-mono mt-1'>
                          {countdownState.nextCaptureAbsolute}
                        </div>
                      )}
                  </div>

                  {/* Manual Capture Button */}
                  <Button
                    onClick={async () => {
                      if (!camera || !isTimelapseRunning) {
                        toast.error("No active timelapse running")
                        return
                      }

                      try {
                        const response = await fetch(
                          `/api/cameras/${camera.id}/capture-now`,
                          {
                            method: "POST",
                          }
                        )

                        if (response.ok) {
                          toast.success("Manual capture triggered!")
                        } else {
                          const error = await response.json()
                          toast.error(
                            error.detail || "Failed to trigger capture"
                          )
                        }
                      } catch (error) {
                        console.error("Error triggering manual capture:", error)
                        toast.error("Failed to trigger capture")
                      }
                    }}
                    disabled={
                      !isTimelapseRunning || camera?.health_status !== "online"
                    }
                    className={`w-full font-medium ${
                      isTimelapseRunning && camera?.health_status === "online"
                        ? "bg-gradient-to-r from-cyan to-purple hover:from-cyan-dark hover:to-purple-dark text-black"
                        : "bg-gray-600 text-gray-400 cursor-not-allowed opacity-50"
                    }`}
                  >
                    <Camera className='w-4 h-4 mr-2' />
                    {!isTimelapseRunning
                      ? "No Active Timelapse"
                      : camera?.health_status !== "online"
                      ? "Camera Offline"
                      : "Take Manual Capture"}
                  </Button>

                  <div className='text-xs text-gray-500 text-center'>
                    {isTimelapseRunning
                      ? "Capture an image right now"
                      : "Start a timelapse to enable manual capture"}
                  </div>
                </div>
              </div>
            </div>

            {/* Camera Settings */}
            <div className='glass-strong rounded-2xl shadow-xl overflow-hidden'>
              <div className='p-6'>
                <h3 className='text-lg font-bold text-white mb-6 flex items-center gap-2'>
                  <Settings className='w-5 h-5 text-accent' />
                  Camera Settings
                </h3>
                <div className='space-y-4'>
                  <div className='glass rounded-lg p-4'>
                    <div className='flex justify-between items-center mb-2'>
                      <span className='text-primary font-medium'>Status</span>
                      <span
                        className={cn(
                          "px-3 py-1 text-xs rounded-full font-medium",
                          camera.status === "active"
                            ? "bg-green-100 text-green-800"
                            : "bg-gray-100 text-gray-800"
                        )}
                      >
                        {camera.status}
                      </span>
                    </div>
                  </div>

                  <div className='glass rounded-lg p-4'>
                    <div className='flex justify-between items-center mb-2'>
                      <span className='text-primary font-medium'>
                        Time Window
                      </span>
                      <span className='text-white font-medium'>
                        {camera.use_time_window &&
                        camera.time_window_start &&
                        camera.time_window_end
                          ? `${camera.time_window_start} - ${camera.time_window_end}`
                          : "Disabled"}
                      </span>
                    </div>
                    <div className='text-xs text-gray-500'>
                      {camera.use_time_window
                        ? "Capture window active"
                        : "24/7 capture mode"}
                    </div>
                  </div>

                  <div className='glass rounded-lg p-4'>
                    <div className='flex justify-between items-center mb-2'>
                      <span className='text-primary font-medium'>Failures</span>
                      <span
                        className={cn(
                          "font-bold",
                          camera.consecutive_failures > 5
                            ? "text-red-400"
                            : camera.consecutive_failures > 2
                            ? "text-yellow-400"
                            : "text-green-400"
                        )}
                      >
                        {camera.consecutive_failures}
                      </span>
                    </div>
                    <div className='text-xs text-gray-500'>consecutive</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Video Generation Settings
            <VideoGenerationSettings
              settings={{
                video_generation_mode: camera.video_generation_mode,
                standard_fps: camera.standard_fps,
                enable_time_limits: camera.enable_time_limits,
                min_time_seconds: camera.min_time_seconds,
                max_time_seconds: camera.max_time_seconds,
                target_time_seconds: camera.target_time_seconds,
                fps_bounds_min: camera.fps_bounds_min,
                fps_bounds_max: camera.fps_bounds_max,
              }}
              onChange={async (newSettings) => {
                try {
                  const response = await fetch(`/api/cameras/${camera.id}`, {
                    method: "PATCH",
                    headers: {
                      "Content-Type": "application/json",
                    },
                    body: JSON.stringify(newSettings),
                  })

                  if (!response.ok) {
                    throw new Error("Failed to update video settings")
                  }

                  // Invalidate cache for settings updates
                  queryClient.invalidateQueries({ queryKey: ['camera', cameraId] })

                  toast.success("Video generation settings updated", {
                    description: "Settings will apply to new timelapses",
                    duration: 4000,
                  })
                } catch (error) {
                  console.error("Error updating video settings:", error)
                  toast.error("Failed to update video settings", {
                    description:
                      error instanceof Error
                        ? error.message
                        : "Unknown error occurred",
                    duration: 6000,
                  })
                }
              }}
              totalImages={stats?.total_images || 0}
              showPreview={true}
              className='w-full'
            /> */}

            {/* Quick Actions */}
            <div className='glass-strong rounded-2xl shadow-xl overflow-hidden'>
              <div className='p-6'>
                <h3 className='text-lg font-bold text-white mb-6 flex items-center gap-2'>
                  <Zap className='w-5 h-5 text-accent' />
                  Quick Actions
                </h3>
                <div className='space-y-3'>
                  <Link
                    href={`/logs?camera_id=${camera.id}`}
                    className='block w-full px-4 py-3 text-center font-medium rounded-lg glass hover:bg-gray-700/50 transition-all text-white border border-gray-600 hover:border-accent'
                  >
                    View Logs
                  </Link>
                  <Link
                    href={`/videos?camera_id=${camera.id}`}
                    className='block w-full px-4 py-3 text-center font-medium rounded-lg glass hover:bg-gray-700/50 transition-all text-white border border-gray-600 hover:border-accent'
                  >
                    View Videos
                  </Link>
                  <button className='w-full px-4 py-3 font-medium rounded-lg glass hover:bg-gray-700/50 transition-all text-white border border-gray-600 hover:border-accent'>
                    Test Connection
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Comprehensive Timelapse Modal */}
      {selectedTimelapse && (
        <TimelapseDetailsModal
          isOpen={timelapseModalOpen}
          onClose={() => {
            setTimelapseModalOpen(false)
            setSelectedTimelapse(null)
          }}
          timelapseId={selectedTimelapse.id}
          cameraName={camera.name}
          onDataUpdate={() => {
            // Refetch data for updates
            refetch()
          }}
        />
      )}

      {/* Settings Modal */}
      <TimelapseSettingsModal
        isOpen={settingsModalOpen}
        onClose={() => setSettingsModalOpen(false)}
        cameraId={cameraId}
        cameraName={camera.name}
        onSettingsUpdate={() => {
          // Refetch data for settings updates
          refetch()
        }}
      />

      {/* Stop Timelapse Confirmation Dialog */}
      <Dialog open={confirmStopOpen} onOpenChange={setConfirmStopOpen}>
        <DialogContent className='glass-opaque border-purple-muted max-w-md'>
          <DialogHeader>
            <DialogTitle className='text-white'>Stop Timelapse</DialogTitle>
          </DialogHeader>
          <div className='space-y-4'>
            <p className='text-grey-light'>
              Are you sure you want to stop the current timelapse for{" "}
              <strong>{camera.name}</strong>?
            </p>
            <p className='text-sm text-yellow-400'>
              This will complete the timelapse and you can generate a video from
              the captured images.
            </p>
            <div className='flex items-center justify-end space-x-3 pt-4'>
              <Button
                variant='outline'
                onClick={() => setConfirmStopOpen(false)}
                className='border-gray-600 text-white hover:bg-gray-700'
              >
                Cancel
              </Button>
              <Button
                onClick={async () => {
                  setConfirmStopOpen(false)
                  await handleStopTimelapse()
                }}
                disabled={actionLoading === "stop"}
                className='bg-failure hover:bg-failure/80 text-white'
              >
                {actionLoading === "stop" ? (
                  <>
                    <div className='w-4 h-4 mr-2 border-2 border-white border-t-transparent rounded-full animate-spin' />
                    Stopping...
                  </>
                ) : (
                  "Stop Timelapse"
                )}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Create New Timelapse Dialog*/}
      <CreateTimelapseDialog
        isOpen={newTimelapseDialogOpen}
        onClose={() => setNewTimelapseDialogOpen(false)}
        onConfirm={handleStartNewTimelapse}
        cameraId={camera.id}
        cameraName={camera.name}
        defaultTimeWindow={{
          start: camera.time_window_start || "06:00:00",
          end: camera.time_window_end || "18:00:00",
          enabled: camera.use_time_window || false,
        }}
      />
    </div>
  )
}
