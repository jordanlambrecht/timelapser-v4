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
  timelapsesLoading: boolean
  timelapsesError: string | null
  videosLoading: boolean
  videosError: string | null

  // Actions
  refetch: () => Promise<void>
  loadTimelapses: () => Promise<void>
  loadVideos: () => Promise<void>
}

export function useCameraDetails(cameraId: number): UseCameraDetailsResult {
  const [camera, setCamera] = useState<CameraWithLastImage | null>(null)
  const [timelapses, setTimelapses] = useState<TimelapseWithDetails[]>([])
  const [videos, setVideos] = useState<VideoWithDetails[]>([])
  const [recentImages, setRecentImages] = useState<ImageForCamera[]>([])
  const [recentActivity, setRecentActivity] = useState<LogForCamera[]>([])
  const [stats, setStats] = useState<CameraDetailStats | null>(null)

  // Main camera loading state
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Lazy loading states for timelapses
  const [timelapsesLoading, setTimelapsesLoading] = useState(false)
  const [timelapsesError, setTimelapsesError] = useState<string | null>(null)
  const [timelapsesLoaded, setTimelapsesLoaded] = useState(false)

  // Lazy loading states for videos
  const [videosLoading, setVideosLoading] = useState(false)
  const [videosError, setVideosError] = useState<string | null>(null)
  const [videosLoaded, setVideosLoaded] = useState(false)

  const fetchCameraDetails = async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch camera data (which now includes statistics)
      const cameraResponse = await fetch(`/api/cameras/${cameraId}`)
      if (!cameraResponse.ok) {
        if (cameraResponse.status === 404) {
          throw new Error("Camera not found")
        }
        throw new Error(`Failed to fetch camera: ${cameraResponse.status}`)
      }
      
      const cameraData = await cameraResponse.json()
      setCamera(cameraData)
      
      // Extract statistics from camera data if available
      if (cameraData.stats) {
        setStats(cameraData.stats)
      }
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

  const loadTimelapses = async (force = false) => {
    if (!force && (timelapsesLoaded || timelapsesLoading)) return

    try {
      setTimelapsesLoading(true)
      setTimelapsesError(null)

      const response = await fetch(`/api/timelapses?camera_id=${cameraId}`)
      if (!response.ok) {
        throw new Error(`Failed to fetch timelapses: ${response.status}`)
      }

      const data = await response.json()
      setTimelapses(data)
      setTimelapsesLoaded(true)
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to load timelapses"
      setTimelapsesError(errorMessage)
    } finally {
      setTimelapsesLoading(false)
    }
  }

  const loadVideos = async (force = false) => {
    if (!force && (videosLoaded || videosLoading)) return

    try {
      setVideosLoading(true)
      setVideosError(null)

      const response = await fetch(`/api/videos?camera_id=${cameraId}`)
      if (!response.ok) {
        throw new Error(`Failed to fetch videos: ${response.status}`)
      }

      const data = await response.json()
      setVideos(data)
      setVideosLoaded(true)
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to load videos"
      setVideosError(errorMessage)
    } finally {
      setVideosLoading(false)
    }
  }

  // Comprehensive refetch that updates all data
  const refetchAll = async () => {
    await Promise.all([
      fetchCameraDetails(),
      timelapsesLoaded ? loadTimelapses(true) : Promise.resolve(),
      videosLoaded ? loadVideos(true) : Promise.resolve(),
    ])
  }

  useEffect(() => {
    if (cameraId) {
      fetchCameraDetails()
      // Auto-load timelapses on camera details page for immediate status visibility
      loadTimelapses()
    }
  }, [cameraId])

  // Derive active timelapse from the timelapses array
  const activeTimelapse =
    timelapses.find((t) => t.status === "running" || t.status === "paused") ||
    null

  return {
    // Data
    camera,
    activeTimelapse,
    timelapses,
    videos,
    recentImages,
    recentActivity,
    stats,

    // State
    loading,
    error,
    timelapsesLoading,
    timelapsesError,
    videosLoading,
    videosError,

    // Actions
    refetch: refetchAll,
    loadTimelapses,
    loadVideos,
  }
}
