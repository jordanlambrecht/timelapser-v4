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
  onTimelapseStarted?: (data: CameraSSEData) => void
  onTimelapsePaused?: (data: CameraSSEData) => void
  onTimelapseResumed?: (data: CameraSSEData) => void
  onTimelapseStopped?: (data: CameraSSEData) => void
  onTimelapseCompleted?: (data: CameraSSEData) => void
  onCameraUpdated?: (data: CameraSSEData) => void
  onCorruptionDetected?: (data: CameraSSEData) => void
  onDegradedModeTriggered?: (data: CameraSSEData) => void
  onCorruptionReset?: (data: CameraSSEData) => void
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
    onTimelapseStarted,
    onTimelapsePaused,
    onTimelapseResumed,
    onTimelapseStopped,
    onTimelapseCompleted,
    onCameraUpdated,
    onCorruptionDetected,
    onDegradedModeTriggered,
    onCorruptionReset,
  } = callbacks

  // Subscribe to image capture events for this camera
  useSSESubscription<CameraSSEData>(
    (event) => event.type === "image_captured" && event.data?.camera_id === cameraId,
    useCallback((event) => {
      onImageCaptured?.(event.data)
    }, [onImageCaptured]),
    [cameraId]
  )

  // Subscribe to camera status changes
  useSSESubscription<CameraSSEData>(
    (event) => event.type === "camera_status_changed" && event.data?.camera_id === cameraId,
    useCallback((event) => {
      onStatusChanged?.(event.data)
    }, [onStatusChanged]),
    [cameraId]
  )

  // Subscribe to timelapse status changes
  useSSESubscription<CameraSSEData>(
    (event) => event.type === "timelapse_status_changed" && event.data?.camera_id === cameraId,
    useCallback((event) => {
      onTimelapseStatusChanged?.(event.data)
    }, [onTimelapseStatusChanged]),
    [cameraId]
  )

  // Subscribe to timelapse started events
  useSSESubscription<CameraSSEData>(
    (event) => event.type === "timelapse_started" && event.data?.camera_id === cameraId,
    useCallback((event) => {
      onTimelapseStarted?.(event.data)
    }, [onTimelapseStarted]),
    [cameraId]
  )

  // Subscribe to timelapse paused events  
  useSSESubscription<CameraSSEData>(
    (event) => event.type === "timelapse_paused" && event.data?.camera_id === cameraId,
    useCallback((event) => {
      onTimelapsePaused?.(event.data)
    }, [onTimelapsePaused]),
    [cameraId]
  )

  // Subscribe to timelapse resumed events
  useSSESubscription<CameraSSEData>(
    (event) => event.type === "timelapse_resumed" && event.data?.camera_id === cameraId,
    useCallback((event) => {
      onTimelapseResumed?.(event.data)
    }, [onTimelapseResumed]),
    [cameraId]
  )

  // Subscribe to timelapse stopped events
  useSSESubscription<CameraSSEData>(
    (event) => event.type === "timelapse_stopped" && event.data?.camera_id === cameraId,
    useCallback((event) => {
      onTimelapseStopped?.(event.data)
    }, [onTimelapseStopped]),
    [cameraId]
  )

  // Subscribe to timelapse completed events
  useSSESubscription<CameraSSEData>(
    (event) => event.type === "timelapse_completed" && event.data?.camera_id === cameraId,
    useCallback((event) => {
      onTimelapseCompleted?.(event.data)
    }, [onTimelapseCompleted]),
    [cameraId]
  )

  // Subscribe to camera updates
  useSSESubscription<CameraSSEData>(
    (event) => event.type === "camera_updated" && event.data?.camera_id === cameraId,
    useCallback((event) => {
      onCameraUpdated?.(event.data)
    }, [onCameraUpdated]),
    [cameraId]
  )

  // Subscribe to corruption detection events
  useSSESubscription<CameraSSEData>(
    (event) => event.type === "image_corruption_detected" && event.data?.camera_id === cameraId,
    useCallback((event) => {
      onCorruptionDetected?.(event.data)
    }, [onCorruptionDetected]),
    [cameraId]
  )

  // Subscribe to degraded mode triggers
  useSSESubscription<CameraSSEData>(
    (event) => event.type === "camera_degraded_mode_triggered" && event.data?.camera_id === cameraId,
    useCallback((event) => {
      onDegradedModeTriggered?.(event.data)
    }, [onDegradedModeTriggered]),
    [cameraId]
  )

  // Subscribe to corruption resets
  useSSESubscription<CameraSSEData>(
    (event) => event.type === "camera_corruption_reset" && event.data?.camera_id === cameraId,
    useCallback((event) => {
      onCorruptionReset?.(event.data)
    }, [onCorruptionReset]),
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
  useSSESubscription<any>(
    (event) => event.type === "camera_added",
    useCallback((event) => {
      onCameraAdded?.(event)
    }, [onCameraAdded])
  )

  useSSESubscription<any>(
    (event) => event.type === "camera_deleted", 
    useCallback((event) => {
      onCameraDeleted?.(event)
    }, [onCameraDeleted])
  )

  // Video generation events
  useSSESubscription<any>(
    (event) => event.type === "video_generated",
    useCallback((event) => {
      onVideoGenerated?.(event)
    }, [onVideoGenerated])
  )

  // Thumbnail regeneration progress
  useSSESubscription<any>(
    (event) => event.type.startsWith("thumbnail_regeneration"),
    useCallback((event) => {
      onThumbnailProgress?.(event)
    }, [onThumbnailProgress])
  )
}
