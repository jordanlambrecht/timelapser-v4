import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/ui/status-badge"
import { CombinedStatusBadge } from "@/components/ui/combined-status-badge"
import { ProgressBorder } from "@/components/ui/progress-border"
import { AnimatedGradientButton } from "@/components/ui/animated-gradient-button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { TimelapseModal } from "@/components/timelapse-modal"
import { VideoNameModal } from "@/components/video-name-modal"
import { VideoProgressModal } from "@/components/video-progress-modal"
import { CreateTimelapseDialog } from "@/components/create-timelapse-dialog"
import { StopTimelapseConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { CameraCardImage } from "@/components/camera-image-unified"
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
  AlertTriangle,
  Shield,
} from "lucide-react"
import { cn } from "@/lib/utils"
import Link from "next/link"
import Image from "next/image"
import { useState, useEffect, useReducer, useCallback, useMemo, memo } from "react"
import { toast } from "@/lib/toast"
import { useCameraCountdown } from "@/hooks/use-camera-countdown"
import { useSettings } from "@/contexts/settings-context"
import { useCameraSSE } from "@/hooks/use-camera-sse"
import { isWithinTimeWindow } from "@/lib/time-utils"
import { TimestampWithWarning } from "@/components/suspicious-timestamp-warning"

// ✅ PERFORMANCE OPTIMIZATION: State consolidation using useReducer
interface CameraCardState {
  imageKey: number
  imageRefetch: (() => Promise<void>) | null
  actualImageCount: number | null
  modals: {
    timelapse: boolean
    videoName: boolean
    videoProgress: boolean
    createTimelapse: boolean
    confirmStop: boolean
  }
  loading: {
    stop: boolean
  }
  currentVideoName: string
}

const initialCameraCardState: CameraCardState = {
  imageKey: 1, // Start with 1 instead of Date.now() to avoid cache busting
  imageRefetch: null,
  actualImageCount: null,
  modals: {
    timelapse: false,
    videoName: false,
    videoProgress: false,
    createTimelapse: false,
    confirmStop: false,
  },
  loading: {
    stop: false,
  },
  currentVideoName: "",
}

type CameraCardAction = 
  | { type: 'INCREMENT_IMAGE_KEY' }
  | { type: 'SET_IMAGE_REFETCH'; payload: (() => Promise<void>) | null }
  | { type: 'SET_IMAGE_COUNT'; payload: number | null }
  | { type: 'TOGGLE_MODAL'; payload: { modal: keyof CameraCardState['modals']; open: boolean } }
  | { type: 'SET_LOADING'; payload: { key: keyof CameraCardState['loading']; loading: boolean } }
  | { type: 'SET_VIDEO_NAME'; payload: string }

function cameraCardReducer(state: CameraCardState, action: CameraCardAction): CameraCardState {
  switch (action.type) {
    case 'INCREMENT_IMAGE_KEY':
      return { ...state, imageKey: state.imageKey + 1 }
    case 'SET_IMAGE_REFETCH':
      return { ...state, imageRefetch: action.payload }
    case 'SET_IMAGE_COUNT':
      return { ...state, actualImageCount: action.payload }
    case 'TOGGLE_MODAL':
      return { 
        ...state, 
        modals: { ...state.modals, [action.payload.modal]: action.payload.open }
      }
    case 'SET_LOADING':
      return { 
        ...state, 
        loading: { ...state.loading, [action.payload.key]: action.payload.loading }
      }
    case 'SET_VIDEO_NAME':
      return { ...state, currentVideoName: action.payload }
    default:
      return state
  }
}

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
    // Corruption detection fields
    corruption_detection_heavy?: boolean
    degraded_mode_active?: boolean
    recent_avg_score?: number
    lifetime_glitch_count?: number
    // Full image object instead of just ID
    last_image?: {
      id: number
      captured_at: string
      file_path: string
      file_size: number | null
      day_number: number
      corruption_score?: number
      is_flagged?: boolean
    } | null
  }
  timelapse?: {
    id: number
    status: string
    image_count: number
    last_capture_at?: string
    name?: string
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

// ✅ PERFORMANCE OPTIMIZATION: Memoized comparison function for React.memo
const arePropsEqual = (prevProps: CameraCardProps, nextProps: CameraCardProps) => {
  return (
    prevProps.camera.id === nextProps.camera.id &&
    prevProps.camera.health_status === nextProps.camera.health_status &&
    prevProps.camera.last_capture_at === nextProps.camera.last_capture_at &&
    prevProps.camera.consecutive_failures === nextProps.camera.consecutive_failures &&
    prevProps.camera.last_image?.captured_at === nextProps.camera.last_image?.captured_at &&
    prevProps.timelapse?.id === nextProps.timelapse?.id &&
    prevProps.timelapse?.status === nextProps.timelapse?.status &&
    prevProps.timelapse?.image_count === nextProps.timelapse?.image_count &&
    prevProps.videos.length === nextProps.videos.length &&
    prevProps.videos.every((v, i) => 
      v.id === nextProps.videos[i]?.id && 
      v.status === nextProps.videos[i]?.status
    )
  )
}

const CameraCardComponent = ({
  camera,
  timelapse,
  videos,
  onToggleTimelapse,
  onPauseTimelapse,
  onResumeTimelapse,
  onEditCamera,
  onDeleteCamera,
  onGenerateVideo,
}: CameraCardProps) => {
  // ✅ PERFORMANCE OPTIMIZATION: Replace 10+ useState with single useReducer
  const [state, dispatch] = useReducer(cameraCardReducer, initialCameraCardState)

  // Use the settings hook for timezone data
  const {
    timezone,
    loading: settingsLoading,
  } = useSettings()
  
  // Default capture interval (5 minutes in seconds)
  const captureInterval = 300

  // ✅ PERFORMANCE OPTIMIZATION: Memoize computed values
  const completedVideos = useMemo(() => 
    videos.filter(v => v.status === "completed"), 
    [videos]
  )

  const completedTimelapses = useMemo(() => completedVideos.length, [completedVideos])

  const isTimelapseRunning = useMemo(() => 
    timelapse?.status === "running", 
    [timelapse?.status]
  )

  const isTimelapsePaused = useMemo(() => 
    timelapse?.status === "paused", 
    [timelapse?.status]
  )

  // Use the new countdown hook for all time formatting
  const {
    countdown,
    lastCaptureText,
    lastCaptureAbsolute,
    nextCaptureAbsolute,
    isNow,
    captureProgress,
  } = useCameraCountdown({
    camera,
    timelapse,
    captureInterval: captureInterval,
  })

  // ✅ PERFORMANCE OPTIMIZATION: Memoized event handlers
  const handleImageRefresh = useCallback(() => {
    // Smart refresh without defeating browser cache
    dispatch({ type: 'INCREMENT_IMAGE_KEY' })
  }, [])

  const handleCaptureNow = useCallback(async () => {
    try {
      const response = await fetch(`/api/cameras/${camera.id}/capture-now`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      })

      const result = await response.json()

      if (response.ok) {
        toast.success("Capture triggered", {
          description: "Image capture has been requested",
          duration: 3000,
        })
      } else {
        toast.error("Capture failed", {
          description: result.error || "Failed to trigger capture",
          duration: 5000,
        })
      }
    } catch (error) {
      toast.error("Capture failed", {
        description: "Network error",
        duration: 5000,
      })
      console.error("Error triggering capture:", error)
    }
  }, [camera.id])

  // ✅ PERFORMANCE OPTIMIZATION: Memoized SSE callbacks
  const sseCallbacks = useMemo(() => ({
    onImageCaptured: (data: any) => {
      // Smart refresh without defeating browser cache
      if (state.imageRefetch) {
        state.imageRefetch()
      } else {
        dispatch({ type: 'INCREMENT_IMAGE_KEY' })
      }

      // Update image count if provided in SSE data
      if (data.image_count !== undefined) {
        dispatch({ type: 'SET_IMAGE_COUNT', payload: data.image_count })
      }

      // Update actual image count from SSE data
      if (data.image_count !== undefined) {
        dispatch({ type: 'SET_IMAGE_COUNT', payload: data.image_count })
      }
    },
    onTimelapseStatusChanged: (data: any) => {
      // Force image refresh when timelapse status changes
      if (state.imageRefetch) {
        state.imageRefetch()
      } else {
        handleImageRefresh()
      }

      // Handle new timelapse started
      if (data.status === "running" && data.timelapse_id) {
        // Reset counters for new timelapse
        dispatch({ type: 'SET_IMAGE_COUNT', payload: 0 })
      }
    },
    onTimelapseStarted: (data: any) => {
      handleImageRefresh()
      dispatch({ type: 'SET_IMAGE_COUNT', payload: 0 })
    },
    onTimelapseStopped: (data: any) => {
      handleImageRefresh()
    },
    onTimelapsePaused: (data: any) => {
      handleImageRefresh()
    },
    onTimelapseResumed: (data: any) => {
      handleImageRefresh()
    },
  }), [state.imageRefetch, handleImageRefresh])

  // 🚀 REAL-TIME SSE EVENTS: Pure SSE-based updates without React Query interference
  useCameraSSE(camera.id, sseCallbacks)

  // 🚀 REMOVED MANUAL POLLING: Replaced with SSE events + cache updates
  // Fetch initial image count on mount only
  useEffect(() => {
    const fetchImageCount = async () => {
      if (!timelapse?.id) return

      try {
        const response = await fetch(
          `/api/images/count?timelapse_id=${timelapse.id}`
        )
        if (response.ok) {
          const data = await response.json()
          dispatch({ type: 'SET_IMAGE_COUNT', payload: data.count })
        }
      } catch (error) {
        console.error("Failed to fetch image count:", error)
      }
    }

    fetchImageCount()
    // NO POLLING - SSE events handle real-time updates
  }, [timelapse?.id])

  // ✅ PERFORMANCE OPTIMIZATION: Memoized video name generation
  const generateDefaultVideoName = useCallback(() => {
    const now = new Date()
    const dateStr = now.toISOString().split('T')[0] // YYYY-MM-DD
    const timeStr = now.toTimeString().split(' ')[0].replace(/:/g, '-') // HH-MM-SS
    return `${camera.name.replace(/[^a-zA-Z0-9]/g, '_')}_${dateStr}_${timeStr}`
  }, [camera.name])

  // ✅ PERFORMANCE OPTIMIZATION: Memoized modal handlers
  const handleGenerateVideoClick = useCallback(() => {
    const defaultName = generateDefaultVideoName()
    dispatch({ type: 'SET_VIDEO_NAME', payload: defaultName })
    dispatch({ type: 'TOGGLE_MODAL', payload: { modal: 'videoName', open: true } })
  }, [generateDefaultVideoName])

  const handleVideoNameConfirm = useCallback(async (videoName: string) => {
    dispatch({ type: 'TOGGLE_MODAL', payload: { modal: 'videoName', open: false } })
    dispatch({ type: 'SET_VIDEO_NAME', payload: videoName })
    dispatch({ type: 'TOGGLE_MODAL', payload: { modal: 'videoProgress', open: true } })

    // Generate video with the provided name
    const generatingToastId = toast.loading("🎬 Generating video...")

    try {
      const response = await fetch("/api/videos/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          timelapse_id: timelapse?.id,
          camera_id: camera.id,
          video_name: videoName,
        }),
      })

      const result = await response.json()

      dispatch({ type: 'TOGGLE_MODAL', payload: { modal: 'videoProgress', open: false } })

      // Dismiss the generating toast
      toast.dismiss(generatingToastId)

      if (result.success) {
        toast.success("🎥 Video generated successfully!", {
          description: `"${videoName}" is ready for download`,
          duration: 5000,
        })
      } else {
        toast.error("Video generation failed", {
          description: result.error || "An unknown error occurred",
          duration: 7000,
        })
      }
    } catch (error) {
      dispatch({ type: 'TOGGLE_MODAL', payload: { modal: 'videoProgress', open: false } })

      // Dismiss the generating toast
      toast.dismiss(generatingToastId)

      console.error("Error generating video:", error)
      toast.error("Failed to generate video", {
        description: "Please try again later",
        duration: 7000,
      })
    }
  }, [timelapse?.id, camera.id, toast])

  // ✅ PERFORMANCE OPTIMIZATION: Use values from earlier memoization
  // completedVideos, completedTimelapses, isTimelapseRunning, isTimelapsePaused are already defined above

  const handlePauseResume = () => {
    if (isTimelapsePaused && onResumeTimelapse) {
      onResumeTimelapse(camera.id)
    } else if (isTimelapseRunning && onPauseTimelapse) {
      onPauseTimelapse(camera.id)
    }
  }

  // Functions generateDefaultVideoName, handleGenerateVideoClick, and handleVideoNameConfirm are already defined above with useCallback

  // TODO: OPTIMIZATION - Replace with optimistic capture from useOptimisticCamera hook
  // const { captureNow } = useOptimisticCamera(camera.id);
  // Then: await captureNow(); // Immediate UI feedback + automatic error handling
  // handleCaptureNow is already defined above with useCallback

  const handleNewTimelapseConfirm = async (config: any) => {
    try {
      const timelapseData = {
        camera_id: camera.id,
        status: "running",
        name: config.name,
        auto_stop_at: config.useAutoStop ? config.autoStopAt : null,
        time_window_start:
          config.timeWindowType === "time" ? config.timeWindowStart : null,
        time_window_end:
          config.timeWindowType === "time" ? config.timeWindowEnd : null,
        use_custom_time_window: config.timeWindowType !== "none",
      }

      // Use the new camera-centric endpoint
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
        dispatch({ type: 'TOGGLE_MODAL', payload: { modal: 'createTimelapse', open: false } })

        // Reset image-related state for new timelapse
        dispatch({ type: 'SET_IMAGE_COUNT', payload: 0 })

        // SSE events will handle real-time updates for the new timelapse
      } else {
        // Timelapse creation failed - state remains unchanged
        toast.error("Failed to start timelapse", {
          description: result.detail || "Failed to start timelapse",
          duration: 5000,
        })
      }
    } catch (error) {
      console.error("Error starting new timelapse:", error)
      toast.error("Failed to start timelapse", {
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        duration: 5000,
      })
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

                {/* Corruption Status Indicator */}
                {camera.degraded_mode_active && (
                  <div className='flex items-center space-x-1 px-2 py-1 bg-red-500/20 border border-red-500/30 rounded-md'>
                    <AlertTriangle className='h-3 w-3 text-red-400' />
                    <span className='text-xs text-red-400 font-medium'>
                      Degraded
                    </span>
                  </div>
                )}

                {/* Quality Score Indicator (if available and not degraded) */}
                {!camera.degraded_mode_active &&
                  camera.recent_avg_score !== undefined && (
                    <div className='flex items-center space-x-1 px-2 py-1 bg-black/30 rounded-md'>
                      <Shield className='h-3 w-3 text-cyan-400' />
                      <span
                        className={`text-xs font-medium ${
                          camera.recent_avg_score >= 90
                            ? "text-green-400"
                            : camera.recent_avg_score >= 70
                            ? "text-blue-400"
                            : camera.recent_avg_score >= 50
                            ? "text-yellow-400"
                            : camera.recent_avg_score >= 30
                            ? "text-orange-400"
                            : "text-red-400"
                        }`}
                      >
                        Q:{camera.recent_avg_score}
                      </span>
                    </div>
                  )}
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
              {/* Capture Now - only show if camera is online and has active timelapse */}
              {camera.health_status === "online" &&
                timelapse?.status === "running" && (
                  <DropdownMenuItem
                    onClick={handleCaptureNow}
                    className='text-white hover:bg-success/20'
                  >
                    <Camera className='w-4 h-4 mr-2' />
                    Capture Now
                  </DropdownMenuItem>
                )}
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

      {/* Active Timelapse Recording Badge */}
      {timelapse?.status === "running" && (
        <div className='px-6 pb-2'>
          <div className='flex items-center space-x-2 p-2 bg-gradient-to-r from-cyan/10 to-purple/10 rounded-lg border border-cyan/20'>
            <div className='flex items-center space-x-2'>
              <div className='w-2 h-2 bg-cyan rounded-full animate-pulse' />
              <Video className='w-4 h-4 text-cyan' />
              <span className='text-sm font-medium text-cyan'>Recording:</span>
            </div>
            <span className='text-sm font-bold text-white truncate'>
              {typeof timelapse?.name === "string" && timelapse.name.length > 0
                ? timelapse.name
                : "Unnamed Timelapse"}
            </span>
          </div>
        </div>
      )}

      {/* Camera Image Preview */}
      <div className='px-6 pb-4'>
        <div className='relative overflow-hidden border aspect-video rounded-xl bg-gray-900/50 border-gray-700/50 backdrop-blur-sm'>
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
          ) : (
            // Has captures - use smart fallback component
            <CameraCardImage
              cameraId={camera.id}
              cameraName={camera.name}
              onRefetchReady={(refetch) => dispatch({ type: 'SET_IMAGE_REFETCH', payload: refetch })}
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

          <ProgressBorder
            progress={timelapse?.status === "running" ? captureProgress : 0}
            color={isNow ? "#06b6d4" : "#10b981"}
            className='flex-1'
          >
            <div
              className={cn(
                "p-3 border bg-black/20 rounded-xl border-purple-muted/20 transition-all duration-300 h-full",
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
                {/* Only show countdown if there's an active timelapse */}
                {timelapse?.status === "running" ||
                timelapse?.status === "paused"
                  ? countdown
                  : "No active timelapse"}
              </p>
              {/* Show absolute time underneath if available and timelapse is active */}
              {nextCaptureAbsolute &&
                !isNow &&
                !isTimelapsePaused &&
                timelapse?.status === "running" && (
                  <p className='mt-1 text-xs text-yellow-400'>
                    {nextCaptureAbsolute}
                  </p>
                )}
              {isTimelapsePaused && !isNow && (
                <p className='mt-1 text-xs text-yellow-400'>Paused</p>
              )}
              {(!timelapse || timelapse?.status === "completed") && !isNow && (
                <p className='mt-1 text-xs text-yellow-400'>Completed</p>
              )}
            </div>
          </ProgressBorder>
        </div>

        {/* Bottom Stats Grid */}
        <div className='grid grid-cols-2 gap-4'>
          <div className='p-3 border bg-black/20 rounded-xl border-purple-muted/20'>
            <div className='flex items-center mb-1 space-x-2'>
              <Zap className='w-4 h-4 text-yellow/70' />
              <p className='text-xs font-medium text-grey-light/60'>Images</p>
            </div>
            {(() => {
              // Debug info available for stats rendering
              return null // Don't interfere with the condition
            })()}
            <div className='space-y-1'>
              <p className='font-bold text-white'>
                {state.actualImageCount !== null
                  ? state.actualImageCount
                  : timelapse?.image_count !== undefined
                  ? timelapse.image_count
                  : "Loading..."}
              </p>
              <p className='text-xs text-cyan-400'>Images captured</p>
            </div>
          </div>

          <div
            className='p-3 transition-all duration-200 border cursor-pointer bg-black/20 rounded-xl border-purple-muted/20 hover:bg-purple/10 hover:border-purple/30'
            onClick={() => dispatch({ type: 'TOGGLE_MODAL', payload: { modal: 'timelapse', open: true } })}
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

        <div className='relative flex justify-between items-center space-x-2 w-full'>
          {/* Pause/Resume button - only show when running or paused and camera is online */}
          {(isTimelapseRunning || isTimelapsePaused) &&
            camera.health_status === "online" && (
              <Button
                onClick={handlePauseResume}
                size='lg'
                variant='outline'
                className='border-gray-600 text-white hover:bg-gray-700 min-w-[80px] grow'
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
          {camera.health_status === "offline" ? (
            <Button
              onClick={() => {}}
              size='lg'
              disabled={true}
              className='bg-gray-600 text-gray-400 cursor-not-allowed opacity-50 font-medium transition-all duration-300 min-w-[140px] grow'
            >
              <Square className='w-4 h-4 mr-1' />
              Offline
            </Button>
          ) : isTimelapseRunning || isTimelapsePaused ? (
            <Button
              onClick={() => dispatch({ type: 'TOGGLE_MODAL', payload: { modal: 'confirmStop', open: true } })}
              size='lg'
              className='bg-failure/80 hover:bg-failure text-white hover:shadow-lg hover:shadow-failure/20 font-medium transition-all duration-300 min-w-[140px] grow'
            >
              <CircleStop className='w-4 h-4 mr-1' />
              Stop
            </Button>
          ) : (
            <AnimatedGradientButton
              onClick={() => dispatch({ type: 'TOGGLE_MODAL', payload: { modal: 'createTimelapse', open: true } })}
              size='lg'
              className='font-medium min-w-[140px] grow'
            >
              <Play className='w-4 h-4 mr-1' />
              Start A New Timelapse
            </AnimatedGradientButton>
          )}
        </div>

        <div className='w-full'>
          {/* Details button */}
          <Button
            asChild
            size='default'
            variant='outline'
            className='w-full border-purple-muted/30 text-white hover:bg-purple/20 hover:border-purple/50 min-w-[80px]'
          >
            <Link href={`/cameras/${camera?.id}`}>
              <Eye className='w-4 h-4 mr-1' />
              Details
            </Link>
          </Button>
        </div>
      </CardContent>

      {/* Timelapse Dialog */}
      <CreateTimelapseDialog
        isOpen={state.modals.createTimelapse}
        onClose={() => dispatch({ type: 'TOGGLE_MODAL', payload: { modal: 'createTimelapse', open: false } })}
        onConfirm={handleNewTimelapseConfirm}
        cameraId={camera.id}
        cameraName={camera.name}
        defaultTimeWindow={{
          start: camera.time_window_start || "06:00:00",
          end: camera.time_window_end || "18:00:00",
          enabled: camera?.use_time_window || false,
        }}
      />

      {/* Timelapse Modal */}
      <TimelapseModal
        isOpen={state.modals.timelapse}
        onClose={() => dispatch({ type: 'TOGGLE_MODAL', payload: { modal: 'timelapse', open: false } })}
        cameraId={camera.id}
        cameraName={camera.name}
      />

      {/* Video Name Modal */}
      <VideoNameModal
        isOpen={state.modals.videoName}
        onClose={() => dispatch({ type: 'TOGGLE_MODAL', payload: { modal: 'videoName', open: false } })}
        onConfirm={handleVideoNameConfirm}
        cameraName={camera.name}
        defaultName={state.currentVideoName}
      />

      {/* Video Progress Modal */}
      <VideoProgressModal
        isOpen={state.modals.videoProgress}
        cameraName={camera.name}
        videoName={state.currentVideoName}
        imageCount={state.actualImageCount || timelapse?.image_count || 0}
      />

      {/* Stop Timelapse Confirmation Dialog */}
      <StopTimelapseConfirmationDialog
        isOpen={state.modals.confirmStop}
        onClose={() => dispatch({ type: 'TOGGLE_MODAL', payload: { modal: 'confirmStop', open: false } })}
        onConfirm={async () => {
          dispatch({ type: 'SET_LOADING', payload: { key: 'stop', loading: true } })
          try {
            // Since stop button only shows when timelapse is running, always pass "running"
            // This ensures handleToggleTimelapse executes the stop logic
            console.log("Stopping timelapse:", {
              cameraId: camera.id,
              timelapseStatus: timelapse?.status,
              timelapseId: timelapse?.id,
            })
            await onToggleTimelapse(camera.id, "running")
            dispatch({ type: 'TOGGLE_MODAL', payload: { modal: 'confirmStop', open: false } })
          } catch (error) {
            console.error("Error stopping timelapse:", error)
            toast.error("Failed to stop timelapse. Please try again.")
          } finally {
            dispatch({ type: 'SET_LOADING', payload: { key: 'stop', loading: false } })
          }
        }}
        isLoading={state.loading.stop}
        cameraName={camera.name}
      />
    </Card>
  )
})

export default CameraCardComponent
