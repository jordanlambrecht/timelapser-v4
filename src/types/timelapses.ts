export interface Timelapse {
  id: number
  camera_id: number
  status: "running" | "stopped" | "paused" | "completed" | "archived"
  name?: string
  start_date?: string
  auto_stop_at?: string
  
  // Time window configuration
  time_window_type: "none" | "time" | "sunrise_sunset"
  time_window_start?: string
  time_window_end?: string
  sunrise_offset_minutes?: number
  sunset_offset_minutes?: number
  use_custom_time_window: boolean
  
  image_count: number
  last_capture_at?: string
  created_at: string
  updated_at: string

  // Video generation settings (inherited from camera, can be overridden)
  video_generation_mode?: string
  standard_fps?: number
  enable_time_limits?: boolean
  min_time_seconds?: number
  max_time_seconds?: number
  target_time_seconds?: number
  fps_bounds_min?: number
  fps_bounds_max?: number
}

export interface CreateTimelapseDialogProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (config: TimelapseConfig) => Promise<void>
  cameraId: number
  cameraName: string
  defaultTimeWindow?: {
    start: string
    end: string
    enabled: boolean
  }
}

export interface TimelapseConfig {
  name: string
  timeWindowType: "none" | "time" | "sunrise_sunset"
  timeWindowStart: string
  timeWindowEnd: string
  sunriseOffsetMinutes: number
  sunsetOffsetMinutes: number
  useAutoStop: boolean
  autoStopAt?: string
}
