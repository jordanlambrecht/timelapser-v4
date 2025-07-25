// src/lib/camera-actions.ts

/**
 * Unified camera timelapse action utilities
 *
 * Provides a clean interface for interacting with the new unified
 * /api/cameras/{camera_id}/timelapse-action endpoint
 */

export type TimelapseAction = "create" | "pause" | "resume" | "end"

export interface TimelapseActionRequest {
  action: TimelapseAction
  timelapse_data?: Record<string, any>
}

export interface TimelapseActionResponse {
  success: boolean
  message: string
  action: string
  camera_id: number
  timelapse_id?: number | null
  timelapse_status?: string | null
  data?: Record<string, any> | null
}

/**
 * Execute a timelapse action using the unified endpoint
 */
export async function executeTimelapseAction(
  cameraId: number,
  action: TimelapseAction,
  timelapseData?: Record<string, any>
): Promise<TimelapseActionResponse> {
  const requestBody: TimelapseActionRequest = {
    action,
    ...(timelapseData && { timelapse_data: timelapseData }),
  }

  const response = await fetch(`/api/cameras/${cameraId}/timelapse-action`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(requestBody),
  })

  const result = await response.json()

  if (!response.ok) {
    throw new Error(
      result.detail || result.message || "Failed to execute timelapse action"
    )
  }

  return result as TimelapseActionResponse
}

/**
 * Convenience function to start a new timelapse
 */
export async function startTimelapse(
  cameraId: number,
  timelapseConfig: Record<string, any>
): Promise<TimelapseActionResponse> {
  return executeTimelapseAction(cameraId, "create", timelapseConfig)
}

/**
 * Convenience function to pause a timelapse
 */
export async function pauseTimelapse(
  cameraId: number
): Promise<TimelapseActionResponse> {
  return executeTimelapseAction(cameraId, "pause")
}

/**
 * Convenience function to resume a timelapse
 */
export async function resumeTimelapse(
  cameraId: number
): Promise<TimelapseActionResponse> {
  return executeTimelapseAction(cameraId, "resume")
}

/**
 * Convenience function to stop/end a timelapse
 */
export async function stopTimelapse(
  cameraId: number
): Promise<TimelapseActionResponse> {
  return executeTimelapseAction(cameraId, "end")
}
