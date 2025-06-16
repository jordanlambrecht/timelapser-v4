import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/ui/status-badge"
import { CombinedStatusBadge } from "@/components/ui/combined-status-badge"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { TimelapseModal } from "@/components/timelapse-modal"
import { VideoNameModal } from "@/components/video-name-modal"
import { VideoProgressModal } from "@/components/video-progress-modal"
import { StopTimelapseConfirmationDialog } from "@/components/ui/confirmation-dialog"
import {
  MoreVertical,
  Play,
  Square,
  Video,
  Clock,
  Camera,
  Zap,
  Eye,
  Image as ImageIcon,
  Pause,
  Timer,
  CircleStop,
} from "lucide-react"
import { cn } from "@/lib/utils"
import Link from "next/link"
import Image from "next/image"
import { useState, useEffect } from "react"
import { toast } from "@/lib/toast"
import {
  useCameraCountdown,
  useCaptureSettings,
} from "@/hooks/use-camera-countdown"
import { isWithinTimeWindow } from "@/lib/time-utils"
import { TimestampWithWarning } from "@/components/suspicious-timestamp-warning"

interface CameraCardProps {
  camera: {
    id: number
    name: string
    rtsp_url: string
    status: string
    health_status: "online" | "offline" | "unknown"
    last_capture_at?: string
    consecutive_failures: number
    time_window_start?: string
    time_window_end?: string
    use_time_window: boolean
    next_capture_at?: string
    // Full image object instead of just ID
    last_image?: {
      id: number
      captured_at: string
      file_path: string
      file_size: number | null
      day_number: number
    } | null
  }
  timelapse?: {
    id: number
    status: string
    image_count: number
    last_capture_at?: string
  }
  videos: Array<{
    id: number
    status: string
    file_size?: number
    duration?: number
    created_at: string
  }>
  onToggleTimelapse: (cameraId: number, currentStatus: string) => void
  onPauseTimelapse?: (cameraId: number) => void
  onResumeTimelapse?: (cameraId: number) => void
  onEditCamera: (cameraId: number) => void
  onDeleteCamera: (cameraId: number) => void
  onGenerateVideo: (cameraId: number) => void
}

export function CameraCard({
  camera,
  timelapse,
  videos,
  onToggleTimelapse,
  onPauseTimelapse,
  onResumeTimelapse,
  onEditCamera,
  onDeleteCamera,
  onGenerateVideo,
}: CameraCardProps) {
  const [imageError, setImageError] = useState(false)
  const [imageLoading, setImageLoading] = useState(true)
  const [imageKey, setImageKey] = useState(Date.now()) // Force image reload
  const [actualImageCount, setActualImageCount] = useState<number | null>(null)
  const [timelapseModalOpen, setTimelapseModalOpen] = useState(false)
  const [videoNameModalOpen, setVideoNameModalOpen] = useState(false)
  const [videoProgressModalOpen, setVideoProgressModalOpen] = useState(false)
  const [currentVideoName, setCurrentVideoName] = useState("")

  // Confirmation dialog state for stopping timelapse
  const [confirmStopOpen, setConfirmStopOpen] = useState(false)
  const [stopLoading, setStopLoading] = useState(false)

  // Use the new capture settings hook for consistent interval data
  const {
    captureInterval,
    timezone,
    loading: settingsLoading,
  } = useCaptureSettings()

  // Use the new countdown hook for all time formatting
  const {
    countdown,
    lastCaptureText,
    lastCaptureAbsolute,
    nextCaptureAbsolute,
    isNow,
  } = useCameraCountdown({
    camera,
    timelapse,
    captureInterval: captureInterval,
  })

  // Server-Sent Events for real-time updates with reconnection
  useEffect(() => {
    let eventSource: EventSource | null = null
    let reconnectTimer: NodeJS.Timeout | null = null
    let reconnectAttempts = 0
    const maxReconnectAttempts = 5
    const baseReconnectDelay = 1000 // 1 second
    let isConnected = false

    const connectSSE = () => {
      try {
        eventSource = new EventSource("/api/events")

        eventSource.onopen = () => {
          console.log(`SSE connected to camera events (camera ${camera.id})`)
          isConnected = true
          reconnectAttempts = 0 // Reset on successful connection
        }

        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)

            // Handle different event types
            switch (data.type) {
              case "image_captured":
                if (data.camera_id === camera.id) {
                  console.log(`New image captured for camera ${camera.id}`)
                  // Only refresh image if this camera now has captures
                  setImageKey(Date.now()) // Force image reload
                  setImageError(false) // Reset error state
                  setImageLoading(true) // Show loading state

                  // Update image count if provided
                  if (data.image_count !== undefined) {
                    setActualImageCount(data.image_count)
                  }
                }
                break
              case "camera_status_changed":
                if (data.camera_id === camera.id) {
                  console.log(
                    `Camera ${camera.id} status changed to ${data.status}`
                  )
                  // Let the parent component handle status updates via normal refresh
                }
                break
              case "timelapse_status_changed":
                if (data.camera_id === camera.id) {
                  console.log(
                    `Timelapse status changed for camera ${camera.id} to ${data.status}`
                  )
                  // Force image refresh when timelapse status changes
                  setImageKey(Date.now())
                  setImageError(false)
                  setImageLoading(true)
                }
                break
              case "connected":
                console.log("SSE connection established")
                break
              case "heartbeat":
                // Keep connection alive
                break
              default:
                console.log("Unknown SSE event:", data.type)
            }
          } catch (error) {
            console.error("Error parsing SSE event:", error)
          }
        }

        eventSource.onerror = (error) => {
          console.error(`SSE connection error for camera ${camera.id}:`, error)
          isConnected = false

          // Close the current connection
          if (eventSource) {
            eventSource.close()
          }

          // Attempt reconnection with exponential backoff
          if (reconnectAttempts < maxReconnectAttempts) {
            const delay = baseReconnectDelay * Math.pow(2, reconnectAttempts)
            console.log(
              `Attempting SSE reconnection in ${delay}ms (attempt ${
                reconnectAttempts + 1
              }/${maxReconnectAttempts})`
            )

            reconnectTimer = setTimeout(() => {
              reconnectAttempts++
              connectSSE()
            }, delay)
          } else {
            console.error(
              `Max SSE reconnection attempts reached for camera ${camera.id}`
            )
          }
        }
      } catch (error) {
        console.error("Failed to create SSE connection:", error)
      }
    }

    // Initial connection
    connectSSE()

    // Cleanup on unmount
    return () => {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
      }
      if (eventSource) {
        eventSource.close()
      }
    }
  }, [camera.id])

  // Fetch accurate image count from images table (reduced frequency)
  useEffect(() => {
    const fetchImageCount = async () => {
      if (!timelapse?.id) return

      try {
        const response = await fetch(
          `/api/images/count?timelapse_id=${timelapse.id}`
        )
        if (response.ok) {
          const data = await response.json()
          setActualImageCount(data.count)
        }
      } catch (error) {
        console.error("Failed to fetch image count:", error)
      }
    }

    fetchImageCount()
    // Only check occasionally as backup - SSE handles real-time updates
    const interval = setInterval(fetchImageCount, 60000) // Every minute as backup
    return () => clearInterval(interval)
  }, [timelapse?.id])

  // Define these variables before the useEffect that uses them
  const completedVideos = videos.filter((v) => v.status === "completed")
  const completedTimelapses = videos.length // Total timelapses (completed videos)
  const isTimelapseRunning = timelapse?.status === "running"
  const isTimelapsePaused = timelapse?.status === "paused"

  const handlePauseResume = () => {
    if (isTimelapsePaused && onResumeTimelapse) {
      onResumeTimelapse(camera.id)
    } else if (isTimelapseRunning && onPauseTimelapse) {
      onPauseTimelapse(camera.id)
    }
  }

  const generateDefaultVideoName = () => {
    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, "-")
    return `${camera.name}_timelapse_${timestamp}`
  }

  const handleGenerateVideoClick = () => {
    const defaultName = generateDefaultVideoName()
    setCurrentVideoName(defaultName)
    setVideoNameModalOpen(true)
  }

  const handleVideoNameConfirm = async (videoName: string) => {
    setVideoNameModalOpen(false)
    setCurrentVideoName(videoName)
    setVideoProgressModalOpen(true)

    // Show generating toast
    const generatingToastId = toast.videoGenerating(videoName)

    try {
      const response = await fetch("/api/videos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          camera_id: camera.id,
          video_name: videoName,
        }),
      })

      const result = await response.json()

      setVideoProgressModalOpen(false)

      // Dismiss the generating toast
      toast.dismiss(generatingToastId)

      if (result.success) {
        toast.videoGenerated(videoName)

        // Refresh data to show new video
        if (onGenerateVideo) {
          onGenerateVideo(camera.id)
        }
      } else {
        toast.error("Video generation failed", {
          description: result.error || "An unknown error occurred",
          duration: 7000,
        })
      }
    } catch (error) {
      setVideoProgressModalOpen(false)

      // Dismiss the generating toast
      toast.dismiss(generatingToastId)

      toast.error("Video generation failed", {
        description: "Network error or server unavailable",
        duration: 7000,
      })
      console.error("Error generating video:", error)
    }
  }

  return (
    <Card className='relative flex flex-col justify-between overflow-hidden glass hover-lift hover:glow group'>
      {/* Animated corner accent */}
      <div className='absolute top-0 right-0 w-24 h-24 opacity-50 bg-gradient-to-bl from-pink/20 to-transparent rounded-bl-3xl' />

      <CardHeader className='relative pb-4'>
        <div className='flex items-start justify-between'>
          <div className='flex-1 space-y-3'>
            <div className='flex items-center space-x-3'>
              <div
                className={cn(
                  "p-2 rounded-xl bg-gradient-to-br transition-all duration-300",
                  camera.health_status === "online"
                    ? "from-success/20 to-cyan/20"
                    : camera.health_status === "offline"
                    ? "from-failure/20 to-purple-dark/20"
                    : "from-warn/20 to-yellow/20"
                )}
              >
                <Camera className='w-5 h-5 text-white' />
              </div>
              <div>
                <Link
                  href={`/cameras/${camera.id}`}
                  className='block transition-colors hover:text-pink'
                >
                  <h3 className='text-lg font-bold text-white transition-colors group-hover:text-pink cursor-pointer'>
                    {camera.name}
                  </h3>
                </Link>
                <CombinedStatusBadge
                  healthStatus={camera.health_status}
                  timelapseStatus={timelapse?.status}
                  isTimelapseRunning={isTimelapseRunning}
                  timeWindowStart={camera.time_window_start}
                  timeWindowEnd={camera.time_window_end}
                  useTimeWindow={camera.use_time_window}
                />
              </div>
            </div>
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant='ghost'
                size='sm'
                className='text-white transition-all duration-300 opacity-0 group-hover:opacity-100 hover:bg-purple-muted/20'
              >
                <MoreVertical className='w-4 h-4' />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align='end'
              className='glass-opaque border-purple-muted'
            >
              <DropdownMenuItem asChild>
                <Link
                  href={`/cameras/${camera.id}`}
                  className='flex items-center text-white cursor-pointer hover:bg-cyan/20 rounded-t-xl'
                >
                  <Eye className='w-4 h-4 mr-2' />
                  View Details
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => onEditCamera(camera.id)}
                className='text-white hover:bg-cyan/20'
              >
                Edit Camera
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={handleGenerateVideoClick}
                className='text-white hover:bg-purple/20'
              >
                Generate Video
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => onDeleteCamera(camera.id)}
                className='text-failure hover:bg-failure/20 rounded-b-xl'
              >
                Delete Camera
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>

      {/* Camera Image Preview */}
      <div className='px-6 pb-4'>
        <div className='relative overflow-hidden border aspect-video rounded-xl bg-gray-900/50 border-gray-700/50 backdrop-blur-sm'>
          {camera.last_image && imageLoading && (
            <div className='absolute inset-0 flex items-center justify-center bg-gray-900/70 backdrop-blur-sm'>
              <div className='flex flex-col items-center space-y-3'>
                <div className='w-8 h-8 border-2 rounded-full border-cyan/30 border-t-cyan animate-spin' />
                <p className='text-xs font-medium text-gray-400'>
                  Loading preview...
                </p>
              </div>
            </div>
          )}

          {!camera.last_image &&
          !camera.last_capture_at &&
          !timelapse?.last_capture_at ? (
            // No captures yet - show placeholder immediately
            <Image
              src='/assets/placeholder-camera.jpg'
              alt={`${camera.name} placeholder`}
              fill
              className='object-cover opacity-60'
              priority
            />
          ) : imageError ? (
            // API call failed - show placeholder
            <Image
              src='/assets/placeholder-camera.jpg'
              alt={`${camera.name} placeholder`}
              fill
              className='object-cover opacity-60'
              priority
            />
          ) : (
            <img
              src={`/api/cameras/${camera.id}/latest-capture?t=${imageKey}`}
              alt={`Last capture from ${camera.name}`}
              className={cn(
                "absolute inset-0 w-full h-full object-cover transition-all duration-500",
                imageLoading ? "opacity-0 scale-105" : "opacity-100 scale-100"
              )}
              onLoad={() => setImageLoading(false)}
              onError={() => {
                setImageError(true)
                setImageLoading(false)
              }}
            />
          )}

          {/* Image overlay with info */}
          <div className='absolute bottom-0 left-0 right-0 p-3 bg-gradient-to-t from-black/80 via-black/20 to-transparent'>
            <div className='flex items-center justify-between text-xs text-white'>
              <div className='flex items-center space-x-2'>
                <div className='p-1 rounded-md bg-white/10 backdrop-blur-sm'>
                  <ImageIcon className='w-3 h-3' />
                </div>
                <span className='font-medium'>Latest frame</span>
              </div>
              {/* <div
                className={cn(
                  "px-2 py-1 rounded-full text-xs font-medium backdrop-blur-sm border",
                  camera.health_status === "online"
                    ? "bg-green-500/20 text-green-300 border-green-500/30"
                    : camera.health_status === "offline"
                    ? "bg-red-500/20 text-red-300 border-red-500/30"
                    : "bg-yellow-500/20 text-yellow-300 border-yellow-500/30"
                )}
              >
                {formatRelativeTime(
                  camera.last_image?.captured_at ||
                    camera.last_capture_at ||
                    timelapse?.last_capture_at
                )}
              </div> */}
            </div>
          </div>

          {/* Status indicator dot */}
          <div className='absolute top-3 right-3'>
            <div
              className={cn(
                "w-3 h-3 rounded-full border-2 border-white/50 transition-all duration-300",
                camera.health_status === "online"
                  ? "bg-green-500 shadow-lg shadow-green-500/50 animate-pulse hover:shadow-xl hover:shadow-green-500/70"
                  : camera.health_status === "offline"
                  ? "bg-red-500 shadow-lg shadow-red-500/50 animate-pulse hover:shadow-xl hover:shadow-red-500/70"
                  : "bg-yellow-500 shadow-lg shadow-yellow-500/50 animate-pulse hover:shadow-xl hover:shadow-yellow-500/70"
              )}
            />
          </div>
        </div>
      </div>

      <CardContent className='space-y-6'>
        {/* Stats Grid with visual enhancement */}
        <div className='grid grid-cols-2 gap-4'>
          <div
            className={cn(
              "p-3 border bg-black/20 rounded-xl border-purple-muted/20 transition-all duration-300",
              isNow && "border-cyan/50 bg-cyan/10 animate-pulse"
            )}
          >
            <div className='flex items-center mb-1 space-x-2'>
              <Clock
                className={cn(
                  "w-4 h-4 text-cyan/70",
                  isNow && "text-cyan animate-pulse"
                )}
              />
              <p className='text-xs font-medium text-grey-light/60'>
                Last Capture
              </p>
            </div>
            <div className='flex items-center space-x-2'>
              <span
                className={cn(
                  "font-bold text-white",
                  isNow && "text-cyan animate-pulse"
                )}
              >
                {lastCaptureText}
              </span>
              <TimestampWithWarning
                timestamp={
                  camera.last_image?.captured_at ||
                  camera.last_capture_at ||
                  timelapse?.last_capture_at
                }
                type='last_capture'
              />
            </div>
            {/* Show absolute time underneath if available */}
            {lastCaptureAbsolute && !isNow && (
              <p className='mt-1 text-xs text-yellow-400'>
                {lastCaptureAbsolute}
              </p>
            )}
            {camera.consecutive_failures > 0 && (
              <p className='mt-1 text-xs text-failure'>
                {camera.consecutive_failures} failures
              </p>
            )}
          </div>

          <div
            className={cn(
              "p-3 border bg-black/20 rounded-xl border-purple-muted/20 transition-all duration-300",
              isNow && "border-cyan/50 bg-cyan/10 animate-pulse"
            )}
          >
            <div className='flex items-center mb-1 space-x-2'>
              <Timer
                className={cn(
                  "w-4 h-4 text-green-400/70",
                  isNow && "text-cyan animate-pulse"
                )}
              />
              <p className='text-xs font-medium text-grey-light/60'>
                Next Capture
              </p>
            </div>
            <p
              className={cn(
                "font-bold text-white",
                isNow && "text-cyan animate-pulse"
              )}
            >
              {countdown}
            </p>
            {/* Show absolute time underneath if available */}
            {nextCaptureAbsolute &&
              !isNow &&
              !isTimelapsePaused &&
              timelapse?.status !== "stopped" &&
              timelapse?.status && (
                <p className='mt-1 text-xs text-yellow-400'>
                  {nextCaptureAbsolute}
                </p>
              )}
            {isTimelapsePaused && !isNow && (
              <p className='mt-1 text-xs text-yellow-400'>Paused</p>
            )}
            {(!timelapse || timelapse?.status === "stopped") && !isNow && (
              <p className='mt-1 text-xs text-yellow-400'>Stopped</p>
            )}
          </div>
        </div>

        {/* Bottom Stats Grid */}
        <div className='grid grid-cols-2 gap-4'>
          <div className='p-3 border bg-black/20 rounded-xl border-purple-muted/20'>
            <div className='flex items-center mb-1 space-x-2'>
              <Zap className='w-4 h-4 text-yellow/70' />
              <p className='text-xs font-medium text-grey-light/60'>Images</p>
            </div>
            <p className='font-bold text-white'>
              {actualImageCount !== null
                ? actualImageCount
                : timelapse?.image_count || 0}
            </p>
          </div>

          <div
            className='p-3 transition-all duration-200 border cursor-pointer bg-black/20 rounded-xl border-purple-muted/20 hover:bg-purple/10 hover:border-purple/30'
            onClick={() => setTimelapseModalOpen(true)}
          >
            <div className='flex items-center mb-1 space-x-2'>
              <Video className='w-4 h-4 text-purple-light/70' />
              <p className='text-xs font-medium text-grey-light/60'>
                Timelapses
              </p>
            </div>
            <p className='font-bold text-white'>{completedTimelapses}</p>
            {completedTimelapses > 0 && (
              <p className='mt-1 text-xs text-purple-light/70'>Click to view</p>
            )}
          </div>
        </div>

        {camera.use_time_window &&
          camera.time_window_start &&
          camera.time_window_end && (
            <div className='flex items-center p-3 space-x-3 border rounded-xl bg-cyan/10 border-cyan/20'>
              <Clock className='flex-shrink-0 w-4 h-4 text-cyan' />
              <div>
                <p className='text-xs font-medium text-cyan/80'>
                  Active Window
                </p>
                <p className='font-mono text-sm text-white'>
                  {camera.time_window_start} - {camera.time_window_end}
                </p>
              </div>
            </div>
          )}

        <div className='flex items-center justify-end pt-2'>
          <div className='flex items-center space-x-2'>
            {/* Pause/Resume button - only show when running or paused and camera is online */}
            {(isTimelapseRunning || isTimelapsePaused) &&
              camera.health_status === "online" && (
                <Button
                  onClick={handlePauseResume}
                  size='sm'
                  variant='outline'
                  className='border-gray-600 text-white hover:bg-gray-700 min-w-[80px]'
                >
                  {isTimelapsePaused ? (
                    <>
                      <Play className='w-4 h-4 mr-1' />
                      Resume
                    </>
                  ) : (
                    <>
                      <Pause className='w-4 h-4 mr-1' />
                      Pause
                    </>
                  )}
                </Button>
              )}

            {/* Main Start/Stop button */}
            <Button
              onClick={() => {
                const isRunning = timelapse?.status === "running"
                const isPaused = timelapse?.status === "paused"

                if (isRunning || isPaused) {
                  // Show confirmation dialog for stopping
                  setConfirmStopOpen(true)
                } else {
                  // Start timelapse directly
                  onToggleTimelapse(camera.id, timelapse?.status || "stopped")
                }
              }}
              size='sm'
              disabled={camera.health_status === "offline"}
              className={cn(
                "font-medium transition-all duration-300 min-w-[80px]",
                camera.health_status === "offline"
                  ? "bg-gray-600 text-gray-400 cursor-not-allowed opacity-50"
                  : isTimelapseRunning || isTimelapsePaused
                  ? "bg-failure/80 hover:bg-failure text-white hover:shadow-lg hover:shadow-failure/20"
                  : "bg-gradient-to-r from-pink to-cyan hover:from-pink-dark hover:to-cyan text-black hover:shadow-lg"
              )}
            >
              {camera.health_status === "offline" ? (
                <>
                  <Square className='w-4 h-4 mr-1' />
                  Offline
                </>
              ) : isTimelapseRunning || isTimelapsePaused ? (
                <>
                  <CircleStop className='w-4 h-4 mr-1' />
                  Stop
                </>
              ) : (
                <>
                  <Play className='w-4 h-4 mr-1' />
                  Start
                </>
              )}
            </Button>
          </div>
        </div>
        <div className='w-full'>
          {/* Details button */}
          <Button
            asChild
            size='default'
            variant='outline'
            className='w-full border-purple-muted/30 text-white hover:bg-purple/20 hover:border-purple/50 min-w-[80px]'
          >
            <Link href={`/cameras/${camera.id}`}>
              <Eye className='w-4 h-4 mr-1' />
              Details
            </Link>
          </Button>
        </div>
      </CardContent>

      {/* Timelapse Modal */}
      <TimelapseModal
        isOpen={timelapseModalOpen}
        onClose={() => setTimelapseModalOpen(false)}
        cameraId={camera.id}
        cameraName={camera.name}
      />

      {/* Video Name Modal */}
      <VideoNameModal
        isOpen={videoNameModalOpen}
        onClose={() => setVideoNameModalOpen(false)}
        onConfirm={handleVideoNameConfirm}
        cameraName={camera.name}
        defaultName={currentVideoName}
      />

      {/* Video Progress Modal */}
      <VideoProgressModal
        isOpen={videoProgressModalOpen}
        cameraName={camera.name}
        videoName={currentVideoName}
        imageCount={actualImageCount || timelapse?.image_count || 0}
      />

      {/* Stop Timelapse Confirmation Dialog */}
      <StopTimelapseConfirmationDialog
        isOpen={confirmStopOpen}
        onClose={() => setConfirmStopOpen(false)}
        onConfirm={async () => {
          setStopLoading(true)
          try {
            // Pass the current timelapse status, not the target status
            await onToggleTimelapse(camera.id, timelapse?.status || "stopped")
            setConfirmStopOpen(false)
          } catch (error) {
            console.error("Error stopping timelapse:", error)
            toast.error("Failed to stop timelapse. Please try again.")
          } finally {
            setStopLoading(false)
          }
        }}
        isLoading={stopLoading}
        cameraName={camera.name}
      />
    </Card>
  )
}
