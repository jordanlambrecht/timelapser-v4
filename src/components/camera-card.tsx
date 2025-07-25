import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { StatusIndicator } from "@/components/ui/status-indicator"
import { AnimatedGradientButton } from "@/components/ui/animated-gradient-button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { TimelapseModal } from "@/components/timelapse-modal"
import { TimelapseCreationModal, type TimelapseForm } from "@/components/timelapse-creation"
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
} from "lucide-react"
import { cn } from "@/lib/utils"
import Link from "next/link"
import Image from "next/image"
import {
  useEffect,
  useReducer,
  useCallback,
  useMemo,
  memo,
  useRef,
} from "react"
import { toast } from "@/lib/toast"
import { useCameraCountdown } from "@/hooks/use-camera-countdown"
// import { useSettings } from "@/contexts/settings-context"
import { useCameraSSE } from "@/hooks/use-camera-sse"
import { useCameraOperations } from "@/hooks/use-camera-operations"
import { TimestampWithWarning } from "@/components/suspicious-timestamp-warning"

// ✅ PERFORMANCE OPTIMIZATION: State consolidation using useReducer
interface CameraCardState {
  imageKey: number
  modals: {
    timelapse: boolean
    createTimelapse: boolean
    confirmStop: boolean
  }
  loading: {
    stop: boolean
  }
}

const initialCameraCardState: CameraCardState = {
  imageKey: 1, // Start with 1 instead of Date.now() to avoid cache busting
  modals: {
    timelapse: false,
    createTimelapse: false,
    confirmStop: false,
  },
  loading: {
    stop: false,
  },
}

type CameraCardAction =
  | { type: "INCREMENT_IMAGE_KEY" }
  | {
      type: "TOGGLE_MODAL"
      payload: { modal: keyof CameraCardState["modals"]; open: boolean }
    }
  | {
      type: "SET_LOADING"
      payload: { key: keyof CameraCardState["loading"]; loading: boolean }
    }

function cameraCardReducer(
  state: CameraCardState,
  action: CameraCardAction
): CameraCardState {
  switch (action.type) {
    case "INCREMENT_IMAGE_KEY":
      return { ...state, imageKey: state.imageKey + 1 }
    case "TOGGLE_MODAL":
      return {
        ...state,
        modals: {
          ...state.modals,
          [action.payload.modal]: action.payload.open,
        },
      }
    case "SET_LOADING":
      return {
        ...state,
        loading: {
          ...state.loading,
          [action.payload.key]: action.payload.loading,
        },
      }
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
    // Camera statistics from API
    stats?: {
      total_images: number
      current_timelapse_images: number
      timelapse_count: number
      total_videos: number
      last_24h_images: number
      success_rate_percent: number | null
      storage_used_mb: number | null
      avg_capture_interval_minutes: number | null
      current_timelapse_name: string | null
      days_since_first_capture: number | null
    }
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
  onEditCamera: (cameraId: number) => void
  onDeleteCamera: (cameraId: number) => void
}

// ✅ PERFORMANCE OPTIMIZATION: Memoized comparison function for React.memo
const arePropsEqual = (
  prevProps: CameraCardProps,
  nextProps: CameraCardProps
) => {
  return (
    prevProps.camera.id === nextProps.camera.id &&
    prevProps.camera.health_status === nextProps.camera.health_status &&
    prevProps.camera.last_capture_at === nextProps.camera.last_capture_at &&
    prevProps.camera.consecutive_failures ===
      nextProps.camera.consecutive_failures &&
    prevProps.camera.last_image?.captured_at ===
      nextProps.camera.last_image?.captured_at &&
    prevProps.timelapse?.id === nextProps.timelapse?.id &&
    prevProps.timelapse?.status === nextProps.timelapse?.status &&
    prevProps.timelapse?.image_count === nextProps.timelapse?.image_count &&
    prevProps.videos.length === nextProps.videos.length &&
    prevProps.videos.every(
      (v, i) =>
        v.id === nextProps.videos[i]?.id &&
        v.status === nextProps.videos[i]?.status
    )
  )
}

const CameraCardComponent = ({
  camera,
  timelapse,
  videos,
  onEditCamera,
  onDeleteCamera,
}: CameraCardProps) => {
  // ✅ PERFORMANCE OPTIMIZATION: Replace 10+ useState with single useReducer
  const [state, dispatch] = useReducer(
    cameraCardReducer,
    initialCameraCardState
  )

  // ✅ FIX: Use useRef to store imageRefetch function to prevent infinite re-renders
  const imageRefetchRef = useRef<(() => Promise<void>) | null>(null)

  // Note: Settings context available if needed for timezone data
  // const { timezone } = useSettings()

  // ✅ DOMAIN COMPLIANCE: Use camera operations hook for all camera-specific actions
  const cameraOps = useCameraOperations()

  // ✅ PERFORMANCE OPTIMIZATION: Memoize computed values
  const completedVideos = useMemo(
    () => videos.filter((v) => v.status === "completed"),
    [videos]
  )

  const isTimelapseRunning = useMemo(
    () => timelapse?.status === "running",
    [timelapse?.status]
  )

  const isTimelapsePaused = useMemo(
    () => timelapse?.status === "paused",
    [timelapse?.status]
  )

  // Use the new countdown hook for all time formatting
  // TODO: According to domain design, capture intervals should be timelapse-specific
  // Once backend provides capture_interval in timelapse data, use that instead
  // For now, use default interval of 5 minutes (300 seconds)
  const defaultCaptureInterval = 300
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
    captureInterval: defaultCaptureInterval,
  })

  const handleCaptureNow = useCallback(async () => {
    await cameraOps.triggerManualCapture(camera.id)
  }, [camera.id, cameraOps])

  // ✅ SSE COMPLIANCE: Enhanced SSE integration with comprehensive event handling
  useCameraSSE(camera.id, {
    onImageCaptured: useCallback((data: { image_count?: number }) => {
      // Force image refresh and update image count
      dispatch({ type: "INCREMENT_IMAGE_KEY" })
      if (imageRefetchRef.current) {
        imageRefetchRef.current()
      }

      // Image count is handled by parent component via SSE
      // The parent will update the timelapse prop which will trigger re-render
    }, []),

    onTimelapseStatusChanged: useCallback(
      (data: { status?: string; timelapse_id?: number }) => {
        // Real-time timelapse status updates
        dispatch({ type: "INCREMENT_IMAGE_KEY" })
        if (imageRefetchRef.current) {
          imageRefetchRef.current()
        }

        // Timelapse status changes are handled by parent component via SSE
        // The parent will update the timelapse prop which will trigger re-render
      },
      []
    ),

    onTimelapseStarted: useCallback(() => {
      dispatch({
        type: "TOGGLE_MODAL",
        payload: { modal: "createTimelapse", open: false },
      })
      // Timelapse data is handled by parent component via SSE
      if (imageRefetchRef.current) {
        imageRefetchRef.current()
      }
    }, []),

    onTimelapseStopped: useCallback(() => {
      // Timelapse data is handled by parent component via SSE
      if (imageRefetchRef.current) {
        imageRefetchRef.current()
      }
    }, []),

    onTimelapsePaused: useCallback(() => {
      if (imageRefetchRef.current) {
        imageRefetchRef.current()
      }
    }, []),

    onTimelapseResumed: useCallback(() => {
      if (imageRefetchRef.current) {
        imageRefetchRef.current()
      }
    }, []),

    onCameraUpdated: useCallback(
      (data: { name?: string; [key: string]: any }) => {
        // Handle camera name updates and other camera property changes
        // This will trigger a re-render with the updated camera data
        // The parent component should handle updating the camera prop
        console.log("Camera updated via SSE:", data)
      },
      []
    ),
  })

  // 🚀 USE EXISTING DATA: Camera stats are already included in props
  // No need for additional API calls - use camera.stats and timelapse.image_count

  // ✅ DOMAIN COMPLIANCE: Use camera operations for pause/resume
  const handlePauseResume = useCallback(async () => {
    if (isTimelapsePaused) {
      await cameraOps.resumeTimelapse(camera.id)
    } else if (isTimelapseRunning) {
      await cameraOps.pauseTimelapse(camera.id)
    }
  }, [isTimelapsePaused, isTimelapseRunning, cameraOps, camera.id])

  const handleNewTimelapseConfirm = useCallback(
    async (config: {
      name: string
      useAutoStop: boolean
      autoStopAt?: string
      timeWindowType: string
      timeWindowStart?: string
      timeWindowEnd?: string
    }) => {
      const timelapseConfig = {
        name: config.name,
        auto_stop_at: config.useAutoStop ? config.autoStopAt : null,
        time_window_start:
          config.timeWindowType === "time" ? config.timeWindowStart : null,
        time_window_end:
          config.timeWindowType === "time" ? config.timeWindowEnd : null,
        use_custom_time_window: config.timeWindowType !== "none",
      }

      const success = await cameraOps.startTimelapse(camera.id, timelapseConfig)

      if (success) {
        dispatch({
          type: "TOGGLE_MODAL",
          payload: { modal: "createTimelapse", open: false },
        })
        // SSE events will handle real-time updates for the new timelapse
      }
    },
    [camera.id, cameraOps]
  )

  const handleStopTimelapseConfirm = useCallback(async () => {
    dispatch({ type: "SET_LOADING", payload: { key: "stop", loading: true } })
    try {
      const success = await cameraOps.stopTimelapse(camera.id)
      if (success) {
        dispatch({
          type: "TOGGLE_MODAL",
          payload: { modal: "confirmStop", open: false },
        })
      }
    } catch (error) {
      console.error("Error stopping timelapse:", error)
      toast.error("Failed to stop timelapse. Please try again.")
    } finally {
      dispatch({
        type: "SET_LOADING",
        payload: { key: "stop", loading: false },
      })
    }
  }, [camera.id, cameraOps])

  // Handle comprehensive timelapse form submission
  const handleTimelapseFormSubmit = useCallback(async (form: TimelapseForm) => {
    try {
      // Convert TimelapseForm to backend API format
      const timelapseData = {
        name: form.name || `Timelapse ${new Date().toISOString().slice(0, 19).replace('T', ' ')}`,
        capture_interval_seconds: form.captureInterval,
        
        // Time window settings
        time_window_type: form.runWindowEnabled 
          ? (form.runWindowType === "sunrise-sunset" ? "sunrise_sunset" : "time")
          : "none",
        time_window_start: form.runWindowEnabled && form.runWindowType === "between" ? form.timeWindowStart : null,
        time_window_end: form.runWindowEnabled && form.runWindowType === "between" ? form.timeWindowEnd : null,
        sunrise_offset_minutes: form.runWindowEnabled && form.runWindowType === "sunrise-sunset" ? form.sunriseOffsetMinutes : null,
        sunset_offset_minutes: form.runWindowEnabled && form.runWindowType === "sunrise-sunset" ? form.sunsetOffsetMinutes : null,
        use_custom_time_window: form.runWindowEnabled,
        
        // Stop time settings
        auto_stop_at: form.stopTimeEnabled && form.stopType === "datetime" ? form.stopDateTime : null,
        
        // Video generation settings
        video_generation_mode: form.videoGenerationMode,
        standard_fps: form.videoStandardFps,
        enable_time_limits: form.videoEnableTimeLimits,
        min_time_seconds: form.videoEnableTimeLimits ? form.videoMinDuration * 60 : null,
        max_time_seconds: form.videoEnableTimeLimits ? form.videoMaxDuration * 60 : null,
        target_time_seconds: form.videoGenerationMode === "target" ? form.videoTargetDuration * 60 : null,
        fps_bounds_min: form.videoFpsMin,
        fps_bounds_max: form.videoFpsMax,
        
        // Video automation settings
        video_automation_mode: form.videoManualOnly ? "manual" : 
                              form.videoPerCapture ? "per_capture" :
                              form.videoScheduled ? "scheduled" :
                              form.videoMilestone ? "milestone" : "manual",
        
        // Generation schedule (for scheduled automation)
        generation_schedule: form.videoScheduled ? {
          type: form.videoScheduleType,
          time: form.videoScheduleTime,
          enabled: true,
          timezone: "UTC"
        } : null,
        
        // Milestone config (for milestone automation)
        milestone_config: form.videoMilestone ? {
          thresholds: [form.videoMilestoneInterval],
          enabled: true,
          reset_on_completion: !form.videoMilestoneOverwrite
        } : null
      }

      // Call the camera timelapse action API to create and start the timelapse
      const response = await fetch(`/api/cameras/${camera.id}/timelapse-action`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          action: "create",
          timelapse_data: timelapseData
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to create timelapse`)
      }

      const newTimelapse = await response.json()
      
      // Close the modal
      dispatch({
        type: "TOGGLE_MODAL",
        payload: { modal: "createTimelapse", open: false },
      })

      toast.success(`Timelapse "${newTimelapse.name || newTimelapse.id}" created successfully!`)
      
    } catch (error) {
      console.error("Failed to create timelapse:", error)
      toast.error(error instanceof Error ? error.message : "Failed to create timelapse")
    }
  }, [camera.id])

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
                <div className='flex items-center space-x-2'>
                  <StatusIndicator
                    status={camera.health_status}
                    size='sm'
                    showIcon
                    iconType='lucide'
                  />
                  <StatusIndicator
                    status={timelapse?.status as "running" | "paused" | "completed" || "completed"}
                    size='sm'
                    showIcon
                    iconType='dot'
                  />
                </div>
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
                    disabled={cameraOps.loading.capture}
                  >
                    <Camera className='w-4 h-4 mr-2' />
                    {cameraOps.loading.capture ? "Capturing..." : "Capture Now"}
                  </DropdownMenuItem>
                )}
              <DropdownMenuItem
                onClick={() => onEditCamera(camera.id)}
                className='text-white hover:bg-cyan/20'
              >
                Edit Camera
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
          {/* Always use CameraCardImage component - it handles fallback logic internally */}
          <CameraCardImage
            cameraId={camera.id}
            cameraName={camera.name}
            className='w-full h-full'
            onRefetchReady={(refetch) => {
              imageRefetchRef.current = refetch
            }}
          />

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
              {/* Only show countdown if there's an active timelapse */}
              {timelapse?.status === "running" || timelapse?.status === "paused"
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
                {timelapse?.image_count !== undefined
                  ? timelapse.image_count
                  : camera.stats?.current_timelapse_images !== undefined
                  ? camera.stats.current_timelapse_images
                  : 0}
              </p>
              <p className='text-xs text-cyan-400'>Current timelapse</p>
              {camera.stats?.total_images !== undefined && (
                <p className='text-xs text-purple-light/70'>
                  {camera.stats.total_images} total lifetime
                </p>
              )}
            </div>
          </div>

          <div
            className='p-3 transition-all duration-200 border cursor-pointer bg-black/20 rounded-xl border-purple-muted/20 hover:bg-purple/10 hover:border-purple/30'
            onClick={() =>
              dispatch({
                type: "TOGGLE_MODAL",
                payload: { modal: "timelapse", open: true },
              })
            }
          >
            <div className='flex items-center mb-1 space-x-2'>
              <Clock className='w-4 h-4 text-purple-light/70' />
              <p className='text-xs font-medium text-grey-light/60'>
                Timelapses
              </p>
            </div>
            <p className='font-bold text-white'>
              {camera.stats?.timelapse_count ?? 0}
            </p>
            {completedVideos.length > 0 && (
              <p className='mt-1 text-xs text-purple-light/70'>Click to view</p>
            )}
          </div>
        </div>

        <div className='relative flex justify-between items-center space-x-2 w-full'>
          {/* Pause/Resume button - only show when running or paused and camera is online */}
          {(isTimelapseRunning || isTimelapsePaused) &&
            camera.health_status === "online" && (
              <Button
                onClick={handlePauseResume}
                size='lg'
                variant='outline'
                className='border-gray-600 text-white hover:bg-gray-700 min-w-[80px] grow'
                disabled={
                  cameraOps.loading.pauseTimelapse ||
                  cameraOps.loading.resumeTimelapse
                }
              >
                {cameraOps.loading.pauseTimelapse ||
                cameraOps.loading.resumeTimelapse ? (
                  <>
                    <Timer className='w-4 h-4 mr-1 animate-spin' />
                    {isTimelapsePaused ? "Resuming..." : "Pausing..."}
                  </>
                ) : isTimelapsePaused ? (
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
              onClick={() =>
                dispatch({
                  type: "TOGGLE_MODAL",
                  payload: { modal: "confirmStop", open: true },
                })
              }
              size='lg'
              className='bg-failure/80 hover:bg-failure text-white hover:shadow-lg hover:shadow-failure/20 font-medium transition-all duration-300 min-w-[140px] grow'
            >
              <CircleStop className='w-4 h-4 mr-1' />
              Stop
            </Button>
          ) : (
            <AnimatedGradientButton
              onClick={() =>
                dispatch({
                  type: "TOGGLE_MODAL",
                  payload: { modal: "createTimelapse", open: true },
                })
              }
              size='lg'
              className='font-medium min-w-[140px] grow'
              disabled={cameraOps.loading.startTimelapse}
            >
              {cameraOps.loading.startTimelapse ? (
                <>
                  <Timer className='w-4 h-4 mr-1 animate-spin' />
                  Starting...
                </>
              ) : (
                <>
                  <Play className='w-4 h-4 mr-1' />
                  Start A New Timelapse
                </>
              )}
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

      {/* Timelapse Creation Modal */}
      <TimelapseCreationModal
        isOpen={state.modals.createTimelapse}
        onClose={() =>
          dispatch({
            type: "TOGGLE_MODAL",
            payload: { modal: "createTimelapse", open: false },
          })
        }
        onSubmit={handleTimelapseFormSubmit}
        cameraId={camera.id}
      />

      {/* Timelapse Modal */}
      <TimelapseModal
        isOpen={state.modals.timelapse}
        onClose={() =>
          dispatch({
            type: "TOGGLE_MODAL",
            payload: { modal: "timelapse", open: false },
          })
        }
        cameraId={camera.id}
        cameraName={camera.name}
      />

      {/* Stop Timelapse Confirmation Dialog */}
      <StopTimelapseConfirmationDialog
        isOpen={state.modals.confirmStop}
        onClose={() =>
          dispatch({
            type: "TOGGLE_MODAL",
            payload: { modal: "confirmStop", open: false },
          })
        }
        onConfirm={handleStopTimelapseConfirm}
        isLoading={state.loading.stop}
        cameraName={camera.name}
      />
    </Card>
  )
}

export const CameraCard = memo(CameraCardComponent, arePropsEqual)
export default CameraCard
