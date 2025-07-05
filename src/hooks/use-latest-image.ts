/**
 * React hook for fetching latest camera image data
 * 
 * Uses the new unified latest-image API endpoint that provides
 * complete metadata + URLs for all image variants in a single call
 */

import { useState, useEffect, useCallback } from 'react'

export interface LatestImageMetadata {
  image_id: number
  captured_at: string
  day_number: number
  timelapse_id: number
  file_size: number | null
  corruption_score: number
  is_flagged: boolean
  urls: {
    full: string
    small: string
    thumbnail: string
    download: string
  }
  metadata: {
    camera_id: number
    has_thumbnail: boolean
    has_small: boolean
    thumbnail_size: number | null
    small_size: number | null
  }
}

export interface LatestImageResponse {
  success: boolean
  data: LatestImageMetadata
  message: string
}

export interface UseLatestImageResult {
  image: LatestImageMetadata | null
  isLoading: boolean
  error: string | null
  refetch: () => Promise<void>
  urls: {
    full: string
    small: string
    thumbnail: string
    download: string
  } | null
}

/**
 * Hook to fetch latest image metadata for a camera
 * 
 * @param cameraId - ID of the camera
 * @param autoRefresh - Whether to auto-refresh every 30 seconds (default: false)
 * @returns Latest image data and utilities
 */
export function useLatestImage(
  cameraId: number | string,
  autoRefresh: boolean = false
): UseLatestImageResult {
  const [image, setImage] = useState<LatestImageMetadata | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchLatestImage = useCallback(async () => {
    try {
      setError(null)
      
      const response = await fetch(`/api/cameras/${cameraId}/latest-image`)
      const data: LatestImageResponse = await response.json()
      
      if (!response.ok) {
        throw new Error(data.message || `HTTP ${response.status}`)
      }
      
      if (data.success && data.data) {
        setImage(data.data)
      } else {
        throw new Error(data.message || 'Failed to fetch latest image')
      }
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      setError(errorMessage)
      setImage(null)
    } finally {
      setIsLoading(false)
    }
  }, [cameraId])

  // Initial fetch and auto-refresh setup
  useEffect(() => {
    fetchLatestImage()
    
    if (autoRefresh) {
      const interval = setInterval(fetchLatestImage, 30000) // 30 seconds
      return () => clearInterval(interval)
    }
  }, [fetchLatestImage, autoRefresh])

  // Prepare URLs for easy access
  const urls = image ? {
    full: `/api/cameras/${cameraId}/latest-image/full`,
    small: `/api/cameras/${cameraId}/latest-image/small`,
    thumbnail: `/api/cameras/${cameraId}/latest-image/thumbnail`,
    download: `/api/cameras/${cameraId}/latest-image/download`
  } : null

  return {
    image,
    isLoading,
    error,
    refetch: fetchLatestImage,
    urls
  }
}

/**
 * Hook specifically for dashboard camera cards (optimized for thumbnails)
 * 
 * @param cameraId - ID of the camera
 * @returns Thumbnail-specific data and URL
 */
export function useLatestImageThumbnail(cameraId: number | string) {
  const { image, isLoading, error, refetch } = useLatestImage(cameraId, false) // No auto-refresh - use SSE events instead
  
  return {
    thumbnailUrl: `/api/cameras/${cameraId}/latest-image/thumbnail`,
    hasImage: !!image,
    isLoading,
    error,
    refetch,
    imageData: image ? {
      id: image.image_id,
      capturedAt: image.captured_at,
      dayNumber: image.day_number,
      corruptionScore: image.corruption_score,
      isFlagged: image.is_flagged
    } : null
  }
}

/**
 * Hook specifically for camera details page (optimized for small images)
 * 
 * @param cameraId - ID of the camera  
 * @returns Small image data and multiple size options
 */
export function useLatestImageDetails(cameraId: number | string) {
  const { image, isLoading, error, refetch, urls } = useLatestImage(cameraId, false)
  
  return {
    smallUrl: `/api/cameras/${cameraId}/latest-image/small`,
    fullUrl: `/api/cameras/${cameraId}/latest-image/full`,
    downloadUrl: `/api/cameras/${cameraId}/latest-image/download`,
    thumbnailUrl: `/api/cameras/${cameraId}/latest-image/thumbnail`,
    hasImage: !!image,
    isLoading,
    error,
    refetch,
    urls,
    imageData: image ? {
      id: image.image_id,
      capturedAt: image.captured_at,
      dayNumber: image.day_number,
      timelapseId: image.timelapse_id,
      fileSize: image.file_size,
      corruptionScore: image.corruption_score,
      isFlagged: image.is_flagged,
      hasVariants: {
        thumbnail: image.metadata.has_thumbnail,
        small: image.metadata.has_small
      }
    } : null
  }
}
