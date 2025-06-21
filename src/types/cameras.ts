import { ImageForCamera } from "./images"
import { LogForCamera } from "./logs"
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
  video_generation_mode: "standard" | "target"
  standard_fps: number
  enable_time_limits: boolean
  min_time_seconds?: number
  max_time_seconds?: number
  target_time_seconds?: number
  fps_bounds_min: number
  fps_bounds_max: number

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

export interface CameraDetailStats {
  totalImages: number
  currentTimelapseImages: number
  currentTimelapseName?: string
  videoCount: number
  totalTimelapses: number
  daysSinceFirstCapture?: number
  storageUsedMb?: number
  last24hImages: number
  successRatePercent?: number
}

export interface CameraDetailsResponse {
  camera: CameraWithLastImage
  active_timelapse?: Timelapse
  timelapses: Timelapse[]
  recent_images: ImageForCamera[]
  videos: Video[]
  recent_activity: LogForCamera[]
  stats: CameraDetailStats
}
