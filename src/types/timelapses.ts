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
  video_generation_mode?: "standard" | "target"
  standard_fps?: number
  enable_time_limits?: boolean
  min_time_seconds?: number
  max_time_seconds?: number
  target_time_seconds?: number
  fps_bounds_min?: number
  fps_bounds_max?: number

  // Video automation settings (inherited from camera, can be overridden)
  video_automation_mode?: "manual" | "per_capture" | "scheduled" | "milestone"
  generation_schedule?: Record<string, any>
  milestone_config?: Record<string, any>
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
  videoSettings?: any
}

// Detailed timelapse interfaces for modals and detailed views
export interface TimelapseDetails {
  id: number
  camera_id: number
  status: string
  name?: string | null
  start_date?: string
  auto_stop_at?: string | null
  image_count: number
  last_capture_at?: string
  created_at: string
  updated_at: string
  // Additional detail fields
  total_size_mb?: number
  estimated_duration?: number
  fps_settings?: any
  // Time window settings
  time_window_start?: string | null
  time_window_end?: string | null
  use_custom_time_window: boolean
  // Video generation settings
  video_generation_mode?: string
  standard_fps?: number
  enable_time_limits?: boolean
  min_time_seconds?: number
  max_time_seconds?: number
  target_time_seconds?: number
  fps_bounds_min?: number
  fps_bounds_max?: number
}

export interface TimelapseVideo {
  id: number
  name: string
  status: "generating" | "completed" | "failed"
  file_path?: string
  file_size?: number | null
  duration?: number
  duration_seconds?: number
  calculated_fps?: number
  created_at: string
  updated_at: string
  settings?: any
  camera_id: number
  image_count?: number | null
  adjustment_reason?: string | null
}

export interface TimelapseImage {
  id: number
  captured_at: string
  file_path: string
  file_size?: number | null
  day_number: number
  thumbnail_path?: string
  corruption_score?: number
  camera_id: number
  timelapse_id: number
  created_at: string
  date_directory?: string | null
  small_path?: string | null
  thumbnail_size?: number | null
  small_size?: number | null
  updated_at: string
}

// Timelapse settings for modal configuration
export interface TimelapseSettings {
  name: string
  auto_stop_enabled: boolean
  auto_stop_at?: string
  video_generation_mode: "standard" | "target"
  standard_fps: number
  enable_time_limits: boolean
  min_time_seconds?: number
  max_time_seconds?: number
  target_time_seconds?: number
  fps_bounds_min: number
  fps_bounds_max: number
}

// Component props interfaces
export interface TimelapseDetailsModalProps {
  isOpen: boolean
  onClose: () => void
  timelapseId: number
  cameraName: string
  onDataUpdate?: () => void
}

export interface TimelapseModalProps {
  isOpen: boolean
  onClose: () => void
  cameraId: number
  cameraName: string
}

export interface TimelapseSettingsModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: (settings: TimelapseSettings) => Promise<void>
  timelapseId: number
  initialSettings?: Partial<TimelapseSettings>
}
