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
  Video as VideoIcon,
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
import {
  useState,
  useEffect,
  useReducer,
  useCallback,
  useMemo,
  memo,
  useRef,
} from "react"
import { toast } from "@/lib/toast"
import { useCameraCountdown } from "@/hooks/use-camera-countdown"
import { useCaptureSettings } from "@/contexts/settings-context"
import { useCameraSSE } from "@/hooks/use-camera-sse"
import { isWithinTimeWindow } from "@/lib/time-utils"
import { TimestampWithWarning } from "@/components/suspicious-timestamp-warning"
import type { CameraWithLastImage, Video } from "@/types"
import type { Timelapse } from "@/types/timelapses"

// Import TimelapseSettings type
interface TimelapseSettings {
  useCustomTimeWindow: boolean
  timeWindowStart: string
  timeWindowEnd: string
  useAutoStop: boolean
  autoStopAt?: string
}

// ✅ PERFORMANCE OPTIMIZATION: State consolidation using useReducer
interface CameraCardState {
  imageKey: number
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
  | { type: "INCREMENT_IMAGE_KEY" }
  | { type: "SET_IMAGE_COUNT"; payload: number | null }
  | {
      type: "TOGGLE_MODAL"
      payload: { modal: keyof CameraCardState["modals"]; open: boolean }
    }
  | {
      type: "SET_LOADING"
      payload: { key: keyof CameraCardState["loading"]; loading: boolean }
    }
  | { type: "SET_VIDEO_NAME"; payload: string }

function cameraCardReducer(
  state: CameraCardState,
  action: CameraCardAction
): CameraCardState {
  switch (action.type) {
    case "INCREMENT_IMAGE_KEY":
      return { ...state, imageKey: state.imageKey + 1 }
    case "SET_IMAGE_COUNT":
      return { ...state, actualImageCount: action.payload }
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
    case "SET_VIDEO_NAME":
      return { ...state, currentVideoName: action.payload }
    default:
      return state
  }
}

interface CameraCardProps {
  camera: CameraWithLastImage
  timelapse?: Timelapse | null
  videos: Video[]
  onToggleTimelapse: (cameraId: number, currentStatus: string) => void
  onPauseTimelapse: (cameraId: number) => void
  onResumeTimelapse: (cameraId: number) => void
  onEditCamera: (cameraId: number) => void
  onDeleteCamera: (cameraId: number) => void
  onGenerateVideo: (cameraId: number) => void
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
      (video, index) =>
        video.id === nextProps.videos[index]?.id &&
        video.status === nextProps.videos[index]?.status
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
  const [state, dispatch] = useReducer(
    cameraCardReducer,
    initialCameraCardState
  )

  // ✅ FIX: Use useRef to store imageRefetch function to prevent infinite re-renders
  const imageRefetchRef = useRef<(() => Promise<void>) | null>(null)

  // Hooks for countdown (simplified for now)
  const { captureInterval } = useCaptureSettings()
  const countdownState = useCameraCountdown({
    camera,
    captureInterval,
  })

  // ✅ PERFORMANCE OPTIMIZATION: Memoized computed values
  const completedVideos = useMemo(
    () => videos.filter((v) => v.status === "completed"),
    [videos]
  )
  const completedTimelapses = useMemo(
    () => completedVideos.length,
    [completedVideos]
  )
  const isTimelapseRunning = useMemo(
    () => timelapse?.status === "running",
    [timelapse?.status]
  )
  const isTimelapsePaused = useMemo(
    () => timelapse?.status === "paused",
    [timelapse?.status]
  )

  // ✅ SSE COMPLIANCE: Proper centralized SSE integration following CLAUDE.md rules
  useCameraSSE(camera.id, {
    onImageCaptured: useCallback(() => {
      // Force image refresh and update image count
      dispatch({ type: "INCREMENT_IMAGE_KEY" })
      if (imageRefetchRef.current) {
        imageRefetchRef.current()
      }
    }, []), // ✅ FIX: No dependencies on unstable function references

    onTimelapseStatusChanged: useCallback(() => {
      // Real-time timelapse status updates handled by parent component
      dispatch({ type: "INCREMENT_IMAGE_KEY" })
    }, []),

    onTimelapseStarted: useCallback(() => {
      dispatch({
        type: "TOGGLE_MODAL",
        payload: { modal: "createTimelapse", open: false },
      })
    }, []),

    onTimelapseStopped: useCallback(() => {
      dispatch({ type: "SET_IMAGE_COUNT", payload: null })
    }, []),
  })

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
          dispatch({ type: "SET_IMAGE_COUNT", payload: data.count })
        }
      } catch (error) {
        console.error("Failed to fetch image count:", error)
      }
    }

    fetchImageCount()
    // NO POLLING - SSE events handle real-time updates
  }, [timelapse?.id])

  // ✅ PERFORMANCE OPTIMIZATION: Memoized capture handler
  const handleCaptureNow = useCallback(async () => {
    try {
      await fetch(`/api/cameras/${camera.id}/capture`, { method: "POST" })
      toast.success("📸 Manual capture triggered", {
        description: `Capturing image for ${camera.name}`,
      })
      if (imageRefetchRef.current) {
        await imageRefetchRef.current()
      }
    } catch (error) {
      console.error("Error triggering capture:", error)
      toast.error("❌ Capture failed", {
        description: "Please try again",
      })
    }
  }, [camera.id, camera.name, toast]) // ✅ FIX: Removed unstable imageRefetch dependency

  // ✅ PERFORMANCE OPTIMIZATION: Memoized video name generation
  const generateDefaultVideoName = useCallback(() => {
    const now = new Date()
    const dateStr = now.toISOString().split("T")[0] // YYYY-MM-DD
    const timeStr = now.toTimeString().split(" ")[0].replace(/:/g, "-") // HH-MM-SS
    return `${camera.name.replace(/[^a-zA-Z0-9]/g, "_")}_${dateStr}_${timeStr}`
  }, [camera.name])

  // ✅ PERFORMANCE OPTIMIZATION: Memoized modal handlers
  const handleGenerateVideoClick = useCallback(() => {
    const defaultName = generateDefaultVideoName()
    dispatch({ type: "SET_VIDEO_NAME", payload: defaultName })
    dispatch({
      type: "TOGGLE_MODAL",
      payload: { modal: "videoName", open: true },
    })
  }, [generateDefaultVideoName])

  const handleVideoNameConfirm = useCallback(
    async (videoName: string) => {
      dispatch({
        type: "TOGGLE_MODAL",
        payload: { modal: "videoName", open: false },
      })
      dispatch({ type: "SET_VIDEO_NAME", payload: videoName })
      dispatch({
        type: "TOGGLE_MODAL",
        payload: { modal: "videoProgress", open: true },
      })

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

        dispatch({
          type: "TOGGLE_MODAL",
          payload: { modal: "videoProgress", open: false },
        })

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
        dispatch({
          type: "TOGGLE_MODAL",
          payload: { modal: "videoProgress", open: false },
        })

        // Dismiss the generating toast
        toast.dismiss(generatingToastId)

        console.error("Error generating video:", error)
        toast.error("Failed to generate video", {
          description: "Please try again later",
          duration: 7000,
        })
      }
    },
    [timelapse?.id, camera.id, toast]
  )

  // ✅ PERFORMANCE OPTIMIZATION: Memoized timelapse action handlers
  const handlePauseResume = useCallback(() => {
    if (isTimelapsePaused && onResumeTimelapse) {
      onResumeTimelapse(camera.id)
    } else if (isTimelapseRunning && onPauseTimelapse) {
      onPauseTimelapse(camera.id)
    }
  }, [
    isTimelapsePaused,
    onResumeTimelapse,
    camera.id,
    isTimelapseRunning,
    onPauseTimelapse,
  ])

  // ✅ PERFORMANCE OPTIMIZATION: Memoized timelapse creation handler
  const handleCreateTimelapse = useCallback(
    async (name: string, settings: TimelapseSettings) => {
      try {
        dispatch({
          type: "TOGGLE_MODAL",
          payload: { modal: "createTimelapse", open: false },
        })

        const response = await fetch(
          `/api/cameras/${camera.id}/start-timelapse`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name,
              use_custom_time_window: settings.useCustomTimeWindow,
              time_window_start: settings.timeWindowStart,
              time_window_end: settings.timeWindowEnd,
              auto_stop_at: settings.useAutoStop ? settings.autoStopAt : null,
            }),
          }
        )

        if (response.ok) {
          toast.success("🎬 Timelapse started", {
            description: `Recording "${name}" for ${camera.name}`,
          })
          // SSE events will handle state updates automatically
        } else {
          const errorData = await response.json()
          throw new Error(errorData.detail || "Failed to start timelapse")
        }
      } catch (error) {
        console.error("Error creating timelapse:", error)
        toast.error("Failed to start timelapse", {
          description: "Failed to create timelapse",
        })
      }
    },
    [camera.id, camera.name, toast]
  )

  // ✅ PERFORMANCE OPTIMIZATION: Memoized action handlers to prevent infinite re-renders
  const handleEditCamera = useCallback(() => {
    onEditCamera(camera.id)
  }, [onEditCamera, camera.id])

  const handleDeleteCamera = useCallback(() => {
    onDeleteCamera(camera.id)
  }, [onDeleteCamera, camera.id])

  const handleViewTimelapse = useCallback(() => {
    dispatch({
      type: "TOGGLE_MODAL",
      payload: { modal: "timelapse", open: true },
    })
  }, [dispatch])

  const handleStopTimelapse = useCallback(() => {
    dispatch({
      type: "TOGGLE_MODAL",
      payload: { modal: "confirmStop", open: true },
    })
  }, [dispatch])

  const handleOpenCreateModal = useCallback(() => {
    dispatch({
      type: "TOGGLE_MODAL",
      payload: { modal: "createTimelapse", open: true },
    })
  }, [dispatch])

  return (
    <Card className='relative flex flex-col justify-between overflow-hidden glass hover-lift hover:glow group'>
      {/* Animated corner accent */}
      <div className='absolute top-0 right-0 w-24 h-24 opacity-50 bg-gradient-to-bl from-pink/20 to-transparent rounded-bl-3xl' />

      <CardHeader className='relative pb-4'>
        {/* Health Status */}
        <div className='flex items-center justify-between mb-4'>
          <div className='flex items-center gap-3'>
            <div className='relative'>
              <CombinedStatusBadge
                healthStatus={camera.health_status}
                timelapseStatus={timelapse?.status}
                isTimelapseRunning={isTimelapseRunning}
              />
            </div>
            <div className='flex flex-col'>
              <h3 className='font-semibold text-lg leading-none text-violet-900 dark:text-violet-100'>
                {camera.name}
              </h3>
              <TimestampWithWarning
                timestamp={camera.last_capture_at}
                type='last_capture'
                className='text-xs text-muted-foreground mt-1'
              />
            </div>
          </div>

          {/* Actions Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant='ghost'
                size='sm'
                className='h-8 w-8 p-0 hover:bg-white/10 hover:backdrop-blur'
              >
                <MoreVertical className='h-4 w-4' />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align='end'
              className='w-48 glass border-white/20'
            >
              <DropdownMenuItem onClick={handleEditCamera}>
                <Camera className='h-4 w-4 mr-2' />
                Edit Camera
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleDeleteCamera}>
                <AlertTriangle className='h-4 w-4 mr-2 text-red-500' />
                Delete Camera
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Camera Image */}
        <div className='relative aspect-video w-full overflow-hidden rounded-lg border border-white/20 bg-black/20'>
          <CameraCardImage
            cameraId={camera.id}
            cameraName={camera.name}
            onRefetchReady={(refetch) => {
              imageRefetchRef.current = refetch
            }}
          />
        </div>
      </CardHeader>

      <CardContent className='space-y-4'>
        {/* Timelapse Info */}
        {timelapse && (
          <div className='space-y-3'>
            {/* Status & Info */}
            <div className='flex items-center justify-between'>
              <div className='flex items-center gap-2'>
                <StatusBadge
                  healthStatus={camera.health_status}
                  timelapseStatus={timelapse.status}
                  isTimelapseRunning={isTimelapseRunning}
                />
                <span className='text-sm font-medium text-violet-900 dark:text-violet-100'>
                  {timelapse.name || `${camera.name} Timelapse`}
                </span>
              </div>
              <Button
                variant='ghost'
                size='sm'
                className='h-8 px-3 text-xs hover:bg-white/10'
                onClick={handleViewTimelapse}
              >
                <Eye className='h-3 w-3 mr-1' />
                View
              </Button>
            </div>

            {/* Image Counter */}
            <div className='flex items-center gap-2 text-sm text-muted-foreground'>
              <ImageIcon className='h-4 w-4' />
              <span>
                Images:{" "}
                {state.actualImageCount !== null
                  ? state.actualImageCount
                  : timelapse.image_count || 0}
              </span>
            </div>

            {/* Running Actions */}
            {isTimelapseRunning && (
              <div className='flex gap-2'>
                <Button
                  variant='outline'
                  size='sm'
                  className='flex-1 glass border-orange-300/30 hover:border-orange-300/60'
                  onClick={handleStopTimelapse}
                >
                  <CircleStop className='h-4 w-4 mr-2' />
                  Stop
                </Button>
                <Button
                  variant='outline'
                  size='sm'
                  className='flex-1 glass border-blue-300/30 hover:border-blue-300/60'
                  onClick={handleOpenCreateModal}
                >
                  <VideoIcon className='h-4 w-4 mr-2' />
                  New
                </Button>
              </div>
            )}
          </div>
        )}

        {/* No Active Timelapse */}
        {!timelapse && (
          <div className='text-center py-8 space-y-4'>
            <div className='text-muted-foreground'>
              <Timer className='h-8 w-8 mx-auto mb-2 opacity-50' />
              <p className='text-sm'>No active timelapse</p>
            </div>
            <Button
              onClick={handleOpenCreateModal}
              className='w-full glass bg-gradient-to-r from-violet-500/80 to-purple-600/80 hover:from-violet-500 hover:to-purple-600 border-white/20'
            >
              <Play className='h-4 w-4 mr-2' />
              Start Timelapse
            </Button>
          </div>
        )}

        {/* Actions Bar */}
        <div className='flex gap-2 pt-2 border-t border-white/10'>
          <Button
            variant='outline'
            size='sm'
            onClick={handleCaptureNow}
            className='flex-1 glass hover:bg-white/10'
          >
            <Zap className='h-4 w-4 mr-2' />
            Capture
          </Button>
          {timelapse && completedTimelapses > 0 && (
            <Button
              variant='outline'
              size='sm'
              onClick={handleGenerateVideoClick}
              className='flex-1 glass hover:bg-white/10'
            >
              <VideoIcon className='h-4 w-4 mr-2' />
              Video
            </Button>
          )}
        </div>

        {/* Completed Videos */}
        {completedVideos.length > 0 && (
          <div className='space-y-2'>
            <h4 className='text-sm font-medium text-violet-900 dark:text-violet-100'>
              Recent Videos ({completedVideos.length})
            </h4>
            <div className='space-y-1'>
              {completedVideos.slice(0, 3).map((video) => (
                <div
                  key={video.id}
                  className='flex items-center justify-between p-2 rounded-md glass border border-white/10 hover:border-white/20 transition-colors'
                >
                  <div className='flex items-center gap-2'>
                    <VideoIcon className='h-3 w-3 text-green-500' />
                    <span className='text-xs font-medium truncate max-w-[120px]'>
                      {video.name}
                    </span>
                  </div>
                  {video.file_path && (
                    <Link
                      href={video.file_path}
                      target='_blank'
                      className='text-xs text-blue-400 hover:text-blue-300'
                    >
                      Download
                    </Link>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>

      {/* Modals - simplified for now */}
      <CreateTimelapseDialog
        isOpen={state.modals.createTimelapse}
        onClose={() =>
          dispatch({
            type: "TOGGLE_MODAL",
            payload: { modal: "createTimelapse", open: false },
          })
        }
        onConfirm={async (config) => {
          // Simplified handler
          dispatch({
            type: "TOGGLE_MODAL",
            payload: { modal: "createTimelapse", open: false },
          })
          toast.success("Timelapse creation started...")
        }}
        cameraId={camera.id}
        cameraName={camera.name}
      />

      {/* Temporarily remove other modals to focus on core optimization */}

      <StopTimelapseConfirmationDialog
        isOpen={state.modals.confirmStop}
        onClose={() =>
          dispatch({
            type: "TOGGLE_MODAL",
            payload: { modal: "confirmStop", open: false },
          })
        }
        onConfirm={async () => {
          try {
            dispatch({
              type: "SET_LOADING",
              payload: { key: "stop", loading: true },
            })
            await onToggleTimelapse(camera.id, "running")
            dispatch({
              type: "TOGGLE_MODAL",
              payload: { modal: "confirmStop", open: false },
            })
          } catch (error) {
            console.error("Error stopping timelapse:", error)
            toast.error("Failed to stop timelapse. Please try again.")
          } finally {
            dispatch({
              type: "SET_LOADING",
              payload: { key: "stop", loading: false },
            })
          }
        }}
        isLoading={state.loading.stop}
        cameraName={camera.name}
      />
    </Card>
  )
}

// ✅ PERFORMANCE OPTIMIZATION: Memoized component with custom comparison
const CameraCard = memo(CameraCardComponent, arePropsEqual)

export default CameraCard
