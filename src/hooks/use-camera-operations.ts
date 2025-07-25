// src/hooks/use-camera-operations.ts
/**
 * Camera Operations Hook
 *
 * Domain: Camera
 * Responsibilities:
 * - Camera CRUD operations
 * - Timelapse lifecycle management (start/pause/resume/stop)
 * - Manual capture triggers
 * - Camera health and connectivity
 * - Latest image access
 *
 * This hook encapsulates all camera-specific operations according to our
 * domain-driven design where cameras own timelapse lifecycle.
 */

import { useCallback, useState } from "react"
import { toast } from "@/lib/toast"
import {
  startTimelapse as startTimelapseAPI,
  pauseTimelapse as pauseTimelapseAPI,
  resumeTimelapse as resumeTimelapseAPI,
  stopTimelapse as stopTimelapseAPI,
} from "@/lib/camera-actions"

export interface CameraOperations {
  // Camera CRUD
  createCamera: (data: CreateCameraData) => Promise<boolean>
  updateCamera: (id: number, data: UpdateCameraData) => Promise<boolean>
  deleteCamera: (id: number) => Promise<boolean>

  // Timelapse lifecycle (Camera domain responsibility)
  startTimelapse: (
    cameraId: number,
    config: TimelapseConfig
  ) => Promise<boolean>
  pauseTimelapse: (cameraId: number) => Promise<boolean>
  resumeTimelapse: (cameraId: number) => Promise<boolean>
  stopTimelapse: (cameraId: number) => Promise<boolean>

  // Manual operations
  triggerManualCapture: (cameraId: number) => Promise<boolean>

  // Health and connectivity
  testConnection: (cameraId: number) => Promise<boolean>
  updateCameraStatus: (
    cameraId: number,
    status: "active" | "inactive"
  ) => Promise<boolean>

  // Loading states
  loading: {
    create: boolean
    update: boolean
    delete: boolean
    startTimelapse: boolean
    pauseTimelapse: boolean
    resumeTimelapse: boolean
    stopTimelapse: boolean
    capture: boolean
    testConnection: boolean
  }
}

export interface CreateCameraData {
  name: string
  rtsp_url: string
  status?: "active" | "inactive"
}

export interface UpdateCameraData {
  name?: string
  rtsp_url?: string
  status?: "active" | "inactive"
}

export interface TimelapseConfig {
  name: string
  auto_stop_at?: string | null
  time_window_start?: string | null
  time_window_end?: string | null
  use_custom_time_window?: boolean
}

export function useCameraOperations(): CameraOperations {
  const [loading, setLoading] = useState({
    create: false,
    update: false,
    delete: false,
    startTimelapse: false,
    pauseTimelapse: false,
    resumeTimelapse: false,
    stopTimelapse: false,
    capture: false,
    testConnection: false,
  })

  const setOperationLoading = useCallback(
    (operation: keyof typeof loading, isLoading: boolean) => {
      setLoading((prev) => ({ ...prev, [operation]: isLoading }))
    },
    []
  )

  const createCamera = useCallback(
    async (data: CreateCameraData): Promise<boolean> => {
      setOperationLoading("create", true)
      try {
        const response = await fetch("/api/cameras", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        })

        if (response.ok) {
          toast.success("Camera created successfully", {
            description: `Camera "${data.name}" has been added`,
            duration: 3000,
          })
          return true
        } else {
          const error = await response.json()
          toast.error("Failed to create camera", {
            description: error.detail || "Unknown error occurred",
            duration: 5000,
          })
          return false
        }
      } catch (error) {
        toast.error("Failed to create camera", {
          description: "Network error or server unavailable",
          duration: 5000,
        })
        console.error("Error creating camera:", error)
        return false
      } finally {
        setOperationLoading("create", false)
      }
    },
    [setOperationLoading]
  )

  const updateCamera = useCallback(
    async (id: number, data: UpdateCameraData): Promise<boolean> => {
      setOperationLoading("update", true)
      try {
        const response = await fetch(`/api/cameras/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        })

        if (response.ok) {
          toast.success("Camera updated successfully", {
            description: "Camera settings have been saved",
            duration: 3000,
          })
          return true
        } else {
          const error = await response.json()
          toast.error("Failed to update camera", {
            description: error.detail || "Unknown error occurred",
            duration: 5000,
          })
          return false
        }
      } catch (error) {
        toast.error("Failed to update camera", {
          description: "Network error or server unavailable",
          duration: 5000,
        })
        console.error("Error updating camera:", error)
        return false
      } finally {
        setOperationLoading("update", false)
      }
    },
    [setOperationLoading]
  )

  const deleteCamera = useCallback(
    async (id: number): Promise<boolean> => {
      setOperationLoading("delete", true)
      try {
        const response = await fetch(`/api/cameras/${id}`, {
          method: "DELETE",
        })

        if (response.ok) {
          toast.success("Camera deleted successfully", {
            description: "Camera has been removed",
            duration: 3000,
          })
          return true
        } else {
          const error = await response.json()
          toast.error("Failed to delete camera", {
            description: error.detail || "Unknown error occurred",
            duration: 5000,
          })
          return false
        }
      } catch (error) {
        toast.error("Failed to delete camera", {
          description: "Network error or server unavailable",
          duration: 5000,
        })
        console.error("Error deleting camera:", error)
        return false
      } finally {
        setOperationLoading("delete", false)
      }
    },
    [setOperationLoading]
  )

  const startTimelapse = useCallback(
    async (cameraId: number, config: TimelapseConfig): Promise<boolean> => {
      setOperationLoading("startTimelapse", true)
      try {
        const result = await startTimelapseAPI(cameraId, {
          name: config.name,
          ...(config.auto_stop_at && { auto_stop_at: config.auto_stop_at }),
          ...(config.time_window_start && {
            time_window_start: config.time_window_start,
          }),
          ...(config.time_window_end && {
            time_window_end: config.time_window_end,
          }),
          ...(config.use_custom_time_window !== undefined && {
            use_custom_time_window: config.use_custom_time_window,
          }),
        })

        if (result.success) {
          toast.success("Timelapse started", {
            description: `New timelapse "${config.name}" is now recording`,
            duration: 3000,
          })
          return true
        } else {
          toast.error("Failed to start timelapse", {
            description: result.message || "Unknown error occurred",
            duration: 5000,
          })
          return false
        }
      } catch (error) {
        toast.error("Failed to start timelapse", {
          description:
            error instanceof Error
              ? error.message
              : "Network error or server unavailable",
          duration: 5000,
        })
        console.error("Error starting timelapse:", error)
        return false
      } finally {
        setOperationLoading("startTimelapse", false)
      }
    },
    [setOperationLoading]
  )

  const pauseTimelapse = useCallback(
    async (cameraId: number): Promise<boolean> => {
      setOperationLoading("pauseTimelapse", true)
      try {
        const result = await pauseTimelapseAPI(cameraId)

        if (result.success) {
          toast.success("Timelapse paused", {
            description: "Recording has been paused",
            duration: 3000,
          })
          return true
        } else {
          toast.error("Failed to pause timelapse", {
            description: result.message || "Unknown error occurred",
            duration: 5000,
          })
          return false
        }
      } catch (error) {
        toast.error("Failed to pause timelapse", {
          description:
            error instanceof Error
              ? error.message
              : "Network error or server unavailable",
          duration: 5000,
        })
        console.error("Error pausing timelapse:", error)
        return false
      } finally {
        setOperationLoading("pauseTimelapse", false)
      }
    },
    [setOperationLoading]
  )

  const resumeTimelapse = useCallback(
    async (cameraId: number): Promise<boolean> => {
      setOperationLoading("resumeTimelapse", true)
      try {
        const result = await resumeTimelapseAPI(cameraId)

        if (result.success) {
          toast.success("Timelapse resumed", {
            description: "Recording has been resumed",
            duration: 3000,
          })
          return true
        } else {
          toast.error("Failed to resume timelapse", {
            description: result.message || "Unknown error occurred",
            duration: 5000,
          })
          return false
        }
      } catch (error) {
        toast.error("Failed to resume timelapse", {
          description:
            error instanceof Error
              ? error.message
              : "Network error or server unavailable",
          duration: 5000,
        })
        console.error("Error resuming timelapse:", error)
        return false
      } finally {
        setOperationLoading("resumeTimelapse", false)
      }
    },
    [setOperationLoading]
  )

  const stopTimelapse = useCallback(
    async (cameraId: number): Promise<boolean> => {
      setOperationLoading("stopTimelapse", true)
      try {
        const result = await stopTimelapseAPI(cameraId)

        if (result.success) {
          toast.success("Timelapse stopped", {
            description: "Recording has been stopped",
            duration: 3000,
          })
          return true
        } else {
          toast.error("Failed to stop timelapse", {
            description: result.message || "Unknown error occurred",
            duration: 5000,
          })
          return false
        }
      } catch (error) {
        toast.error("Failed to stop timelapse", {
          description:
            error instanceof Error
              ? error.message
              : "Network error or server unavailable",
          duration: 5000,
        })
        console.error("Error stopping timelapse:", error)
        return false
      } finally {
        setOperationLoading("stopTimelapse", false)
      }
    },
    [setOperationLoading]
  )

  const triggerManualCapture = useCallback(
    async (cameraId: number): Promise<boolean> => {
      setOperationLoading("capture", true)
      try {
        const response = await fetch(`/api/cameras/${cameraId}/capture-now`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        })

        if (response.ok) {
          toast.success("Capture triggered", {
            description: "Image capture has been requested",
            duration: 3000,
          })
          return true
        } else {
          const error = await response.json()
          toast.error("Capture failed", {
            description: error.detail || "Unknown error occurred",
            duration: 5000,
          })
          return false
        }
      } catch (error) {
        toast.error("Capture failed", {
          description: "Network error or server unavailable",
          duration: 5000,
        })
        console.error("Error triggering capture:", error)
        return false
      } finally {
        setOperationLoading("capture", false)
      }
    },
    [setOperationLoading]
  )

  const testConnection = useCallback(
    async (cameraId: number): Promise<boolean> => {
      setOperationLoading("testConnection", true)
      try {
        const response = await fetch(
          `/api/cameras/${cameraId}/test-connection`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
          }
        )

        if (response.ok) {
          const result = await response.json()
          if (result.success) {
            toast.success("Connection test passed", {
              description: "Camera is reachable and responding",
              duration: 3000,
            })
            return true
          } else {
            toast.error("Connection test failed", {
              description: result.error || "Camera is not responding",
              duration: 5000,
            })
            return false
          }
        } else {
          const error = await response.json()
          toast.error("Connection test failed", {
            description: error.detail || "Unknown error occurred",
            duration: 5000,
          })
          return false
        }
      } catch (error) {
        toast.error("Connection test failed", {
          description: "Network error or server unavailable",
          duration: 5000,
        })
        console.error("Error testing connection:", error)
        return false
      } finally {
        setOperationLoading("testConnection", false)
      }
    },
    [setOperationLoading]
  )

  const updateCameraStatus = useCallback(
    async (
      cameraId: number,
      status: "active" | "inactive"
    ): Promise<boolean> => {
      setOperationLoading("update", true)
      try {
        const response = await fetch(`/api/cameras/${cameraId}/status`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status_data: status }),
        })

        if (response.ok) {
          toast.success("Camera status updated", {
            description: `Camera is now ${status}`,
            duration: 3000,
          })
          return true
        } else {
          const error = await response.json()
          toast.error("Failed to update camera status", {
            description: error.detail || "Unknown error occurred",
            duration: 5000,
          })
          return false
        }
      } catch (error) {
        toast.error("Failed to update camera status", {
          description: "Network error or server unavailable",
          duration: 5000,
        })
        console.error("Error updating camera status:", error)
        return false
      } finally {
        setOperationLoading("update", false)
      }
    },
    [setOperationLoading]
  )

  return {
    createCamera,
    updateCamera,
    deleteCamera,
    startTimelapse,
    pauseTimelapse,
    resumeTimelapse,
    stopTimelapse,
    triggerManualCapture,
    testConnection,
    updateCameraStatus,
    loading,
  }
}
