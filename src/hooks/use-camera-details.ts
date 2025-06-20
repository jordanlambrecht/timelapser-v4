// src/hooks/use-camera-details.ts
"use client"

import { useState, useEffect } from "react"
import { toast } from "@/lib/toast"

// TypeScript interfaces for the comprehensive response
interface CameraWithLastImage {
  id: number
  name: string
  rtsp_url: string
  status: string
  health_status: string
  last_capture_at: string | null
  consecutive_failures: number
  use_time_window: boolean
  time_window_start: string | null
  time_window_end: string | null
  active_timelapse_id: number | null
  // Video generation settings
  video_generation_mode: "standard" | "target"
  standard_fps: number
  enable_time_limits: boolean
  min_time_seconds?: number | null
  max_time_seconds?: number | null
  target_time_seconds?: number | null
  fps_bounds_min: number
  fps_bounds_max: number
  // Image data
  last_image?: {
    id: number
    captured_at: string
    file_path: string
    file_size: number | null
    day_number: number
    thumbnail_path?: string | null
    thumbnail_size?: number | null
    small_path?: string | null
    small_size?: number | null
  } | null
  created_at: string
  updated_at: string
}

interface TimelapseWithDetails {
  id: number
  camera_id: number
  status: string
  name: string | null
  start_date: string
  image_count: number
  last_capture_at: string | null
  created_at: string
  updated_at: string
  camera_name: string
  // Video settings
  video_generation_mode?: "standard" | "target"
  standard_fps?: number
  enable_time_limits?: boolean
  min_time_seconds?: number | null
  max_time_seconds?: number | null
  target_time_seconds?: number | null
  fps_bounds_min?: number
  fps_bounds_max?: number
  // Time window settings
  auto_stop_at?: string | null
  time_window_start?: string | null
  time_window_end?: string | null
  use_custom_time_window?: boolean
}

interface VideoWithDetails {
  id: number
  camera_id: number
  name: string
  status: string
  file_path: string | null
  file_size: number | null
  duration_seconds: number | null
  created_at: string
  updated_at: string
  camera_name: string
  image_count?: number | null
  images_start_date?: string | null
  images_end_date?: string | null
  settings?: Record<string, any>
}

interface ImageForCamera {
  id: number
  captured_at: string
  file_path: string
  file_size: number | null
  day_number: number
  thumbnail_path?: string | null
  thumbnail_size?: number | null
  small_path?: string | null
  small_size?: number | null
}

interface LogForCamera {
  id: number
  level: string
  message: string
  timestamp: string
  camera_id?: number | null
}

interface CameraDetailStats {
  total_images: number
  current_timelapse_images: number
  total_videos: number
  timelapse_count: number
  days_since_first_capture: number
  storage_used_mb: number
  current_timelapse_name: string | null
  current_timelapse_status: string | null
}

interface CameraDetailsResponse {
  camera: CameraWithLastImage
  active_timelapse: TimelapseWithDetails | null
  timelapses: TimelapseWithDetails[]
  recent_images: ImageForCamera[]
  videos: VideoWithDetails[]
  recent_activity: LogForCamera[]
  stats: CameraDetailStats
}

interface UseCameraDetailsResult {
  // Data
  camera: CameraWithLastImage | null
  activeTimelapse: TimelapseWithDetails | null
  timelapses: TimelapseWithDetails[]
  videos: VideoWithDetails[]
  recentImages: ImageForCamera[]
  recentActivity: LogForCamera[]
  stats: CameraDetailStats | null

  // State
  loading: boolean
  error: string | null

  // Actions
  refetch: () => Promise<void>
}

export function useCameraDetails(cameraId: number): UseCameraDetailsResult {
  const [data, setData] = useState<CameraDetailsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchCameraDetails = async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await fetch(`/api/cameras/${cameraId}/details`)

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error("Camera not found")
        }
        throw new Error(`Failed to fetch camera details: ${response.status}`)
      }

      const result: CameraDetailsResponse = await response.json()

      setData(result)
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to fetch camera details"
      setError(errorMessage)
      toast.error("Failed to load camera details", {
        description: errorMessage,
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (cameraId) {
      fetchCameraDetails()
    }
  }, [cameraId])

  return {
    // Data
    camera: data?.camera || null,
    activeTimelapse: data?.active_timelapse || null,
    timelapses: data?.timelapses || [],
    videos: data?.videos || [],
    recentImages: data?.recent_images || [],
    recentActivity: data?.recent_activity || [],
    stats: data?.stats || null,

    // State
    loading,
    error,

    // Actions
    refetch: fetchCameraDetails,
  }
}
