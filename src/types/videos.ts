export interface Video {
  id: number
  camera_id: number
  name: string
  settings?: {
    total_images?: number
    fps?: number
    [key: string]: any
  }
  file_path?: string
  status: "generating" | "completed" | "failed"
  image_count?: number
  file_size?: number
  duration_seconds?: number
  images_start_date?: string
  images_end_date?: string
  created_at: string
  updated_at: string
  calculated_fps?: number
  target_duration?: number
  actual_duration?: number
  fps_was_adjusted?: boolean
  adjustment_reason?: string
}

// Video generation settings
export interface VideoGenerationSettings {
  video_generation_mode: "standard" | "target"
  standard_fps: number
  enable_time_limits: boolean
  min_time_seconds?: number | null
  max_time_seconds?: number | null
  target_time_seconds?: number | null
  fps_bounds_min: number
  fps_bounds_max: number
}

// Video generation calculation results
export interface CalculationPreview {
  estimated_fps: number
  estimated_duration: number
  duration_formatted: string
  fps_was_adjusted: boolean
  adjustment_reason?: string
  error?: string
}

// Video overlay settings
export interface OverlaySettings {
  enabled: boolean
  position: "top-left" | "top-right" | "bottom-left" | "bottom-right" | "center"
  font_size: number
  font_color: string
  background_color: string
  format: string
}

// Component props interfaces
export interface VideoGenerationSettingsProps {
  settings: VideoGenerationSettings
  onChange: (settings: VideoGenerationSettings) => void
  isInherited?: boolean
  onResetToDefaults?: () => void
  totalImages?: number
  className?: string
  showPreview?: boolean
}

export interface VideoOverlayConfigProps {
  settings: OverlaySettings
  onChange: (settings: OverlaySettings) => void
  showPreview?: boolean
}
