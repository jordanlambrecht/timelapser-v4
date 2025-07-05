// src/hooks/use-camera-details.ts
"use client"

import { useState, useEffect } from "react"
import { toast } from "@/lib/toast"
import type {
  CameraWithLastImage,
  CameraDetailsResponse,
  TimelapseWithDetails,
  VideoWithDetails,
  ImageForCamera,
  LogForCamera,
  CameraDetailStats,
} from "@/types/api"

export interface UseCameraDetailsResult {
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

  // Derive active timelapse from the timelapses array
  const activeTimelapse = data?.timelapses?.find(
    (t) => t.status === "running" || t.status === "paused"
  ) || null

  return {
    // Data
    camera: data?.camera || null,
    activeTimelapse,
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
