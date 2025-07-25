// src/hooks/use-timelapse-details.ts
"use client"

import { useState, useEffect } from "react"
import { toast } from "@/lib/toast"
import type { TimelapseDetails, TimelapseVideo, TimelapseImage } from "@/types/timelapses"
import type { CameraWithLastImage } from "@/types/api"

export interface UseTimelapseDetailsResult {
  timelapse: TimelapseDetails | null
  camera: CameraWithLastImage | null
  images: TimelapseImage[]
  videos: TimelapseVideo[]
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

export function useTimelapseDetails(timelapseId: number): UseTimelapseDetailsResult {
  const [timelapse, setTimelapse] = useState<TimelapseDetails | null>(null)
  const [camera, setCamera] = useState<CameraWithLastImage | null>(null)
  const [images, setImages] = useState<TimelapseImage[]>([])
  const [videos, setVideos] = useState<TimelapseVideo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchTimelapseDetails = async () => {
    try {
      setLoading(true)
      setError(null)

      // Fetch timelapse details
      const timelapseResponse = await fetch(`/api/timelapses/${timelapseId}`)
      if (!timelapseResponse.ok) {
        if (timelapseResponse.status === 404) {
          throw new Error("Timelapse not found")
        }
        throw new Error(`Failed to fetch timelapse: ${timelapseResponse.status}`)
      }

      const timelapseData = await timelapseResponse.json()
      const timelapseDetails = timelapseData.data || timelapseData

      setTimelapse(timelapseDetails)

      // Fetch camera details
      if (timelapseDetails.camera_id) {
        const cameraResponse = await fetch(`/api/cameras/${timelapseDetails.camera_id}`)
        if (cameraResponse.ok) {
          const cameraData = await cameraResponse.json()
          setCamera(cameraData.data || cameraData)
        }
      }

      // Fetch recent images for this timelapse
      const imagesResponse = await fetch(`/api/images?timelapse_id=${timelapseId}&limit=20`)
      if (imagesResponse.ok) {
        const imagesData = await imagesResponse.json()
        setImages(imagesData.data || [])
      }

      // Fetch videos for this timelapse
      const videosResponse = await fetch(`/api/timelapses/${timelapseId}/videos`)
      if (videosResponse.ok) {
        const videosData = await videosResponse.json()
        setVideos(videosData.data || [])
      }

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch timelapse details"
      setError(errorMessage)
      toast.error("Failed to load timelapse details", {
        description: errorMessage,
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (timelapseId) {
      fetchTimelapseDetails()
    }
  }, [timelapseId])

  return {
    timelapse,
    camera,
    images,
    videos,
    loading,
    error,
    refetch: fetchTimelapseDetails,
  }
}
