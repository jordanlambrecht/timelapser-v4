// src/lib/fastapi-client.ts
// Updated TypeScript interfaces to match FastAPI Pydantic models exactly

import {
  ImageForCamera,
  CameraWithLastImage,
  VideoWithDetails,
  TimelapseWithDetails as ApiTimelapseWithDetails,
  LogForCamera,
  CameraDetailStats,
  CameraDetailsResponse,
  VideoGenerationJob,
  CorruptionLog,
  CameraHealthStatus,
} from "@/types/api"

// Camera interfaces - only define what's not in the API types
export interface CameraBase {
  name: string
  rtsp_url: string
  status: "active" | "inactive"
  time_window_start: string | null // Time as HH:MM:SS string
  time_window_end: string | null // Time as HH:MM:SS string
  use_time_window: boolean
  video_generation_mode: "standard" | "target"
  standard_fps: number
  enable_time_limits: boolean
  min_time_seconds: number | null
  max_time_seconds: number | null
  target_time_seconds: number | null
  fps_bounds_min: number
  fps_bounds_max: number
  corruption_detection_heavy: boolean
}

export interface CameraCreate extends CameraBase {}

export interface CameraUpdate {
  name?: string
  rtsp_url?: string
  status?: "active" | "inactive"
  time_window_start?: string | null
  time_window_end?: string | null
  use_time_window?: boolean
  video_generation_mode?: "standard" | "target"
  standard_fps?: number
  enable_time_limits?: boolean
  min_time_seconds?: number | null
  max_time_seconds?: number | null
  target_time_seconds?: number | null
  fps_bounds_min?: number
  fps_bounds_max?: number
  corruption_detection_heavy?: boolean
}

export interface Camera extends CameraBase {
  id: number
  health_status: "online" | "offline" | "unknown"
  last_capture_at: string | null // ISO datetime string
  last_capture_success: boolean | null
  consecutive_failures: number
  next_capture_at: string | null // When next capture is scheduled
  active_timelapse_id: number | null
  created_at: string // ISO datetime string
  updated_at: string // ISO datetime string
  // Corruption detection fields
  lifetime_glitch_count: number
  consecutive_corruption_failures: number
  degraded_mode_active: boolean
  last_degraded_at: string | null
  // Include full image object instead of just ID
  last_image: ImageForCamera | null
}

/* Removed local CameraWithLastImage interface to resolve import conflict.
   Use the imported CameraWithLastImage from "@/types/api" instead. */

export interface CameraStats {
  total_images: number
  last_24h_images: number
  avg_capture_interval_minutes: number | null
  success_rate_percent: number | null
  storage_used_mb: number | null
}

export interface CameraWithStats extends CameraWithLastImage {
  stats: CameraStats
}

// Timelapse interfaces
export interface TimelapseBase {
  camera_id: number
  status: "running" | "stopped" | "paused"
}

export interface TimelapseCreate extends TimelapseBase {}

export interface TimelapseUpdate {
  status?: "running" | "stopped" | "paused"
}

export interface Timelapse extends TimelapseBase {
  id: number
  start_date: string | null // Date as YYYY-MM-DD string
  image_count: number
  last_capture_at: string | null // ISO datetime string
  created_at: string // ISO datetime string
  updated_at: string // ISO datetime string
}

export interface TimelapseWithDetails extends Timelapse {
  camera_name: string
}

// Video interfaces
export interface VideoBase {
  camera_id: number
  name: string
  settings: Record<string, any>
}

export interface VideoCreate extends VideoBase {}

export interface VideoUpdate {
  name?: string
  file_path?: string | null
  status?: "generating" | "completed" | "failed"
  settings?: Record<string, any>
  image_count?: number | null
  file_size?: number | null
  duration_seconds?: number | null
  images_start_date?: string | null // Date as YYYY-MM-DD string
  images_end_date?: string | null // Date as YYYY-MM-DD string
}

export interface Video extends VideoBase {
  id: number
  file_path: string | null
  status: "generating" | "completed" | "failed"
  image_count: number | null
  file_size: number | null
  duration_seconds: number | null
  images_start_date: string | null // Date as YYYY-MM-DD string
  images_end_date: string | null // Date as YYYY-MM-DD string
  created_at: string // ISO datetime string
  updated_at: string // ISO datetime string
}

// Removed local VideoWithDetails interface to resolve import conflict.
// Use the imported VideoWithDetails from "@/types/api" instead.

// Image interfaces
export interface ImageBase {
  camera_id: number
  timelapse_id: number
  file_path: string
  day_number: number
  file_size: number | null
}

export interface ImageCreate extends ImageBase {}

export interface Image extends ImageBase {
  id: number
  captured_at: string // ISO datetime string
  created_at: string // ISO datetime string
}

export interface ImageWithDetails extends Image {
  camera_name?: string | null
  timelapse_status?: string | null
}

// Settings interfaces
export interface SettingBase {
  key: string
  value: string
}

export interface SettingCreate extends SettingBase {}

export interface SettingUpdate {
  value: string
}

export interface Setting extends SettingBase {
  id: number
  created_at: string // ISO datetime string
  updated_at: string // ISO datetime string
}

// Log interfaces
export interface LogBase {
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL"
  message: string
  camera_id: number | null
}

export interface LogCreate extends LogBase {}

export interface Log extends LogBase {
  id: number
  timestamp: string // ISO datetime string
}

// API Response interfaces
export interface APIResponse<T> {
  data?: T
  message?: string
  error?: string
}

export interface APIError {
  detail: string
}

// FastAPI client configuration
export const FASTAPI_BASE_URL =
  process.env.FASTAPI_URL ||
  process.env.NEXT_PUBLIC_FASTAPI_URL ||
  "http://localhost:8000"

// API client helper functions
export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${FASTAPI_BASE_URL}${endpoint}`

  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  })

  if (!response.ok) {
    const error: APIError = await response.json()
    throw new Error(error.detail || "API request failed")
  }

  return response.json()
}

// API client functions
export const api = {
  // Camera endpoints
  cameras: {
    list: () => apiRequest<CameraWithLastImage[]>("/api/cameras"),
    get: (id: number) => apiRequest<CameraWithLastImage>(`/api/cameras/${id}`),
    create: (data: CameraCreate) =>
      apiRequest<Camera>("/api/cameras", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: number, data: CameraUpdate) =>
      apiRequest<Camera>(`/api/cameras/${id}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      apiRequest<{ message: string }>(`/api/cameras/${id}`, {
        method: "DELETE",
      }),
    // Camera-centric timelapse management
    startTimelapse: (cameraId: number, data?: any) =>
      apiRequest<{ success: boolean; timelapse_id: number; message: string }>(
        `/api/cameras/${cameraId}/start-timelapse`,
        {
          method: "POST",
          body: JSON.stringify(data || {}),
        }
      ),
    pauseTimelapse: (cameraId: number) =>
      apiRequest<{ success: boolean; timelapse_id: number; message: string }>(
        `/api/cameras/${cameraId}/pause-timelapse`,
        {
          method: "POST",
        }
      ),
    resumeTimelapse: (cameraId: number) =>
      apiRequest<{ success: boolean; timelapse_id: number; message: string }>(
        `/api/cameras/${cameraId}/resume-timelapse`,
        {
          method: "POST",
        }
      ),
    stopTimelapse: (cameraId: number) =>
      apiRequest<{ success: boolean; timelapse_id: number; message: string }>(
        `/api/cameras/${cameraId}/stop-timelapse`,
        {
          method: "POST",
        }
      ),
    completeTimelapse: (cameraId: number) =>
      apiRequest<{ success: boolean; timelapse_id: number; message: string }>(
        `/api/cameras/${cameraId}/complete-timelapse`,
        {
          method: "POST",
        }
      ),
  },

  // Timelapse data endpoints (for querying, not lifecycle management)
  timelapses: {
    list: (cameraId?: number) => {
      const params = cameraId ? `?camera_id=${cameraId}` : ""
      return apiRequest<ApiTimelapseWithDetails[]>(`/api/timelapses${params}`)
    },
    updateStatus: (cameraId: number, data: TimelapseUpdate) =>
      apiRequest<{ timelapse_id: number; status: string }>(
        `/api/timelapses/${cameraId}`,
        {
          method: "PUT",
          body: JSON.stringify(data),
        }
      ),
  },

  // Video endpoints
  videos: {
    list: (cameraId?: number) => {
      const params = cameraId ? `?camera_id=${cameraId}` : ""
      return apiRequest<VideoWithDetails[]>(`/api/videos${params}`)
    },
    get: (id: number) => apiRequest<VideoWithDetails>(`/api/videos/${id}`),
    create: (data: VideoCreate) =>
      apiRequest<{ video_id: number; status: string }>("/api/videos", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    delete: (id: number) =>
      apiRequest<{ message: string }>(`/api/videos/${id}`, {
        method: "DELETE",
      }),
  },

  // Settings endpoints
  settings: {
    list: () => apiRequest<Record<string, string>>("/api/settings"),
    update: (key: string, value: string) =>
      apiRequest<{ message: string }>("/api/settings", {
        method: "PUT",
        body: JSON.stringify({ key, value }),
      }),
  },
}
