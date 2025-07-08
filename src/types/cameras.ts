import {
  ImageForCamera,
  CameraDetailStats,
  CameraDetailsResponse,
  LogForCamera,
} from "./api"
import { Timelapse } from "./timelapses"
import { Video } from "./videos"

export interface Camera {
  id: number
  name: string
  rtsp_url: string
  status: "active" | "inactive"
  health_status: "online" | "offline" | "unknown"
  last_capture_at?: string
  last_capture_success?: boolean
  consecutive_failures: number
  next_capture_at?: string
  active_timelapse_id?: number
  created_at: string
  updated_at: string

  time_window_start?: string
  time_window_end?: string
  use_time_window: boolean

  // Video generation settings (FPS/duration)
  video_generation_mode: "standard" | "target"
  standard_fps: number
  enable_time_limits: boolean
  min_time_seconds?: number
  max_time_seconds?: number
  target_time_seconds?: number
  fps_bounds_min: number
  fps_bounds_max: number

  // Video automation settings (when to generate)
  video_automation_mode: "manual" | "per_capture" | "scheduled" | "milestone"
  generation_schedule?: Record<string, any>
  milestone_config?: Record<string, any>

  // Corruption detection fields
  corruption_detection_heavy: boolean
  lifetime_glitch_count: number
  consecutive_corruption_failures: number
  degraded_mode_active: boolean
  last_degraded_at?: string
}

export interface CameraWithLastImage extends Camera {
  last_image?: ImageForCamera
}

// Camera Component Props
export interface CameraCardProps {
  camera: CameraWithLastImage
  onEditCamera: (camera: Camera) => void
  onDeleteCamera: (camera: Camera) => void
  onCreateTimelapse: (cameraId: number) => void
  onOpenVideoModal: (camera: Camera) => void
  className?: string
}

export interface CameraCardAutomationBadgeProps {
  camera: Camera
  className?: string
}

export interface CameraImageWithFallbackProps {
  cameraId: number
  cameraName: string
  imageKey: number
}

// Hook Interfaces
export interface CameraCountdownProps {
  cameraId: number
  intervalSeconds: number
  onCountdownUpdate?: (timeRemaining: number) => void
}

export interface CountdownState {
  timeRemaining: number
  isActive: boolean
  lastCapture?: string
  nextCapture?: string
}

export interface CameraSSEData {
  camera_id: number
  event_type: string
  data: any
  timestamp: string
}

export interface CameraSSECallbacks {
  onCameraUpdate?: (data: CameraSSEData) => void
  onImageCapture?: (data: CameraSSEData) => void
  onError?: (error: Event) => void
  onConnect?: () => void
  onDisconnect?: () => void
}

export interface CorruptionStats {
  total_images: number
  flagged_images: number
  flagged_percentage: number
  avg_corruption_score: number
  last_24h_flagged: number
  cameras_affected: number
}

export interface CameraCorruptionStats extends CorruptionStats {
  camera_id: number
  camera_name: string
  recent_flagged: ImageForCamera[]
}

export interface CorruptionLogEntry {
  timestamp: string
  camera_id: number
  camera_name: string
  image_id: number
  corruption_score: number
  details: object | null
}

export interface UseCameraDetailsResult {
  data: CameraDetailsResponse | null
  isLoading: boolean
  error: string | null
  refetch: () => Promise<void>
}

// Data Interfaces
export interface CorruptionTestResult {
  imageId: number
  originalScore: number
  newScore: number
  flagged: boolean
  details: object | null
}
