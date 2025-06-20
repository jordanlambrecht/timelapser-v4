import { useCallback } from "react"
import { useSSESubscription } from "@/contexts/sse-context"

export interface CameraSSEData {
  camera_id: number
  image_count?: number
  status?: string
  health_status?: string
  timelapse_id?: number
  [key: string]: any
}

export interface CameraSSECallbacks {
  onImageCaptured?: (data: CameraSSEData) => void
  onStatusChanged?: (data: CameraSSEData) => void
  onTimelapseStatusChanged?: (data: CameraSSEData) => void
  onCameraUpdated?: (data: CameraSSEData) => void
}

/**
 * Hook for subscribing to camera-specific SSE events
 * Replaces individual EventSource connections in camera components
 */
export function useCameraSSE(cameraId: number, callbacks: CameraSSECallbacks) {
  const {
    onImageCaptured,
    onStatusChanged,
    onTimelapseStatusChanged,
    onCameraUpdated,
  } = callbacks

  // Subscribe to image capture events for this camera
  useSSESubscription(
    (event) => event.type === "image_captured" && event.camera_id === cameraId,
    useCallback((event) => {
      onImageCaptured?.(event)
    }, [onImageCaptured]),
    [cameraId]
  )

  // Subscribe to camera status changes
  useSSESubscription(
    (event) => event.type === "camera_status_changed" && event.camera_id === cameraId,
    useCallback((event) => {
      onStatusChanged?.(event)
    }, [onStatusChanged]),
    [cameraId]
  )

  // Subscribe to timelapse status changes
  useSSESubscription(
    (event) => event.type === "timelapse_status_changed" && event.camera_id === cameraId,
    useCallback((event) => {
      onTimelapseStatusChanged?.(event)
    }, [onTimelapseStatusChanged]),
    [cameraId]
  )

  // Subscribe to camera updates
  useSSESubscription(
    (event) => event.type === "camera_updated" && event.camera_id === cameraId,
    useCallback((event) => {
      onCameraUpdated?.(event)
    }, [onCameraUpdated]),
    [cameraId]
  )
}

/**
 * Hook for subscribing to global dashboard events
 * For dashboard-wide updates not specific to a single camera
 */
export function useDashboardSSE(callbacks: {
  onCameraAdded?: (data: any) => void
  onCameraDeleted?: (data: any) => void
  onVideoGenerated?: (data: any) => void
  onThumbnailProgress?: (data: any) => void
}) {
  const { onCameraAdded, onCameraDeleted, onVideoGenerated, onThumbnailProgress } = callbacks

  // Camera management events
  useSSESubscription(
    (event) => event.type === "camera_added",
    useCallback((event) => {
      onCameraAdded?.(event)
    }, [onCameraAdded])
  )

  useSSESubscription(
    (event) => event.type === "camera_deleted", 
    useCallback((event) => {
      onCameraDeleted?.(event)
    }, [onCameraDeleted])
  )

  // Video generation events
  useSSESubscription(
    (event) => event.type === "video_generated",
    useCallback((event) => {
      onVideoGenerated?.(event)
    }, [onVideoGenerated])
  )

  // Thumbnail regeneration progress
  useSSESubscription(
    (event) => event.type.startsWith("thumbnail_regeneration"),
    useCallback((event) => {
      onThumbnailProgress?.(event)
    }, [onThumbnailProgress])
  )
}
