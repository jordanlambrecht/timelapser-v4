// src/types/api.ts
// Centralized TypeScript interfaces for Timelapser v4 API

// ============================================================================
// CAMERA TYPES
// ============================================================================

export interface CameraWithLastImage {
  // Core camera fields
  id: number
  name: string
  rtsp_url: string
  status: string
  created_at: string
  updated_at: string

  // Health and capture status
  health_status: string
  last_capture_at: string | null
  last_capture_success: boolean
  consecutive_failures: number
  next_capture_at: string | null

  // Time window settings
  time_window_start: string | null
  time_window_end: string | null
  use_time_window: boolean

  // Video generation settings
  video_generation_mode: "standard" | "target"
  standard_fps: number
  enable_time_limits: boolean
  min_time_seconds: number | null
  max_time_seconds: number | null
  target_time_seconds: number | null
  fps_bounds_min: number
  fps_bounds_max: number

  // Video automation settings
  video_automation_mode: "manual" | "per_capture" | "scheduled" | "milestone"
  generation_schedule: any | null // JSONB field
  milestone_config: any | null // JSONB field

  // Corruption detection settings
  corruption_detection_heavy: boolean
  corruption_score: number | null
  is_flagged: boolean
  lifetime_glitch_count: number
  consecutive_corruption_failures: number

  // Active timelapse relationship
  active_timelapse_id: number | null
  timelapse_id: number | null
  timelapse_status: string | null

  // Last image data
  last_image?: {
    id: number
    captured_at: string
    file_path: string
    file_size: number | null
    day_number: number
    thumbnail_path: string | null
    thumbnail_size: number | null
    small_path: string | null
    small_size: number | null
  } | null
}

export interface CameraCreate {
  name: string
  rtsp_url: string
  use_time_window?: boolean
  time_window_start?: string | null
  time_window_end?: string | null
}

export interface CameraUpdate {
  name?: string
  rtsp_url?: string
  use_time_window?: boolean
  time_window_start?: string | null
  time_window_end?: string | null
  video_generation_mode?: "standard" | "target"
  standard_fps?: number
  enable_time_limits?: boolean
  min_time_seconds?: number | null
  max_time_seconds?: number | null
  target_time_seconds?: number | null
  fps_bounds_min?: number
  fps_bounds_max?: number
  video_automation_mode?: "manual" | "per_capture" | "scheduled" | "milestone"
  generation_schedule?: any
  milestone_config?: any
  corruption_detection_heavy?: boolean
}

// ============================================================================
// TIMELAPSE TYPES
// ============================================================================

export interface TimelapseWithDetails {
  // Core timelapse fields
  id: number
  camera_id: number
  status: string
  name: string | null
  start_date: string
  image_count: number
  last_capture_at: string | null
  created_at: string
  updated_at: string

  // Additional relationships
  camera_name: string

  // Auto-stop functionality
  auto_stop_at: string | null

  // Time window settings (can override camera settings)
  time_window_start: string | null
  time_window_end: string | null
  use_custom_time_window: boolean
  time_window_type: string | null
  sunrise_offset_minutes: number | null
  sunset_offset_minutes: number | null

  // Video generation settings (inherit/override from camera)
  video_generation_mode: "standard" | "target" | null
  standard_fps: number | null
  enable_time_limits: boolean | null
  min_time_seconds: number | null
  max_time_seconds: number | null
  target_time_seconds: number | null
  fps_bounds_min: number | null
  fps_bounds_max: number | null

  // Video automation settings (inherit/override from camera)
  video_automation_mode: "manual" | "per_capture" | "scheduled" | "milestone" | null
  generation_schedule: any | null
  milestone_config: any | null

  // Corruption tracking
  glitch_count: number | null
  total_corruption_score: number | null
}

export interface TimelapseCreate {
  camera_id: number
  name?: string | null
  auto_stop_at?: string | null
  use_custom_time_window?: boolean
  time_window_start?: string | null
  time_window_end?: string | null
}

export interface TimelapseUpdate {
  name?: string | null
  status?: string
  auto_stop_at?: string | null
  use_custom_time_window?: boolean
  time_window_start?: string | null
  time_window_end?: string | null
  video_generation_mode?: "standard" | "target" | null
  standard_fps?: number | null
  enable_time_limits?: boolean | null
  min_time_seconds?: number | null
  max_time_seconds?: number | null
  target_time_seconds?: number | null
  fps_bounds_min?: number | null
  fps_bounds_max?: number | null
  video_automation_mode?: "manual" | "per_capture" | "scheduled" | "milestone" | null
  generation_schedule?: any
  milestone_config?: any
}

// ============================================================================
// VIDEO TYPES
// ============================================================================

export interface VideoWithDetails {
  // Core video fields
  id: number
  camera_id: number
  name: string
  status: string
  file_path: string | null
  file_size: number | null
  duration_seconds: number | null
  created_at: string
  updated_at: string

  // Relationships
  camera_name: string
  timelapse_id: number | null

  // Image range information
  image_count: number | null
  images_start_date: string | null
  images_end_date: string | null

  // Video generation metadata
  calculated_fps: number | null
  target_duration: number | null
  actual_duration: number | null
  fps_was_adjusted: boolean | null
  adjustment_reason: string | null

  // Automation tracking
  trigger_type: string | null
  job_id: number | null

  // Legacy settings field
  settings?: Record<string, any>
}

export interface VideoCreate {
  camera_id: number
  name: string
  settings?: Record<string, any>
}

export interface VideoGenerationRequest {
  camera_id: number
  video_name?: string | null
}

// ============================================================================
// IMAGE TYPES
// ============================================================================

export interface ImageForCamera {
  id: number
  captured_at: string
  file_path: string
  file_size: number | null
  day_number: number
  thumbnail_path: string | null
  thumbnail_size: number | null
  small_path: string | null
  small_size: number | null

  // Corruption data
  corruption_score: number | null
  is_flagged: boolean | null
  corruption_details: any | null
}

// ============================================================================
// LOG TYPES
// ============================================================================

export interface LogForCamera {
  id: number
  level: string
  message: string
  timestamp: string
  camera_id: number | null
}

// ============================================================================
// STATS TYPES
// ============================================================================

export interface CameraDetailStats {
  total_images: number
  current_timelapse_images: number
  current_timelapse_name: string | null
  total_videos: number
  timelapse_count: number
  days_since_first_capture: number | null
  storage_used_mb: number
  last_24h_images: number
  success_rate_percent: number
  avg_capture_interval_minutes: number | null
  current_timelapse_status: string | null
}

export interface DashboardStats {
  total_cameras: number
  active_cameras: number
  total_images: number
  total_videos: number
  total_timelapses: number
  storage_used_gb: number
  system_health: "healthy" | "warning" | "error"
  last_updated: string
}

// ============================================================================
// RESPONSE TYPES
// ============================================================================

export interface CameraDetailsResponse {
  camera: CameraWithLastImage
  timelapses: TimelapseWithDetails[]
  videos: VideoWithDetails[]
  recent_images: ImageForCamera[]
  recent_activity: LogForCamera[]
  stats: CameraDetailStats
}

// ============================================================================
// AUTOMATION TYPES
// ============================================================================

export interface VideoGenerationJob {
  id: number
  timelapse_id: number
  trigger_type: string
  status: string
  priority: string
  created_at: string
  started_at: string | null
  completed_at: string | null
  error_message: string | null
  video_path: string | null
  video_id: number | null
  settings: any | null
}

export interface VideoAutomationSettings {
  video_automation_mode: "manual" | "per_capture" | "scheduled" | "milestone"
  generation_schedule?: {
    type: "daily" | "weekly" | "custom"
    time?: string
    timezone?: string
    cron_expression?: string
  }
  milestone_config?: {
    thresholds: number[]
    enabled: boolean
    reset_on_completion?: boolean
  }
}

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

// ============================================================================
// CORRUPTION TYPES
// ============================================================================

export interface CorruptionLog {
  id: number
  camera_id: number
  image_id: number | null
  corruption_score: number
  fast_score: number | null
  heavy_score: number | null
  detection_details: any | null
  action_taken: string
  processing_time_ms: number | null
  created_at: string
}

export interface CameraHealthStatus {
  camera_id: number
  health_status: string
  last_capture_at: string | null
  consecutive_failures: number
  connectivity_test_result: any | null
  corruption_rate: number | null
  degraded_mode_active: boolean | null
  last_degraded_at: string | null
}

// ============================================================================
// SSE EVENT TYPES
// ============================================================================

export interface SSEEvent {
  type: string
  data: any
  timestamp: string
}

export interface CameraSSEEvents {
  camera_created: { camera_id: number; camera_name: string; rtsp_url: string }
  camera_updated: { camera_id: number; camera_name: string; changes: any }
  camera_deleted: { camera_id: number; camera_name: string }
  camera_status_updated: { camera_id: number; status: string; error_message?: string }
  camera_health_updated: { camera_id: number; health_data: any }
  manual_capture_completed: { camera_id: number; capture_result: any }
}

export interface VideoSSEEvents {
  video_created: { video_id: number; camera_id: number; video_name: string; status: string }
  video_deleted: { video_id: number; video_name: string; camera_id: number }
  video_generation_scheduled: { 
    camera_id: number
    timelapse_id: number
    timelapse_name: string
    job_id: number
    trigger_type: string
  }
}
