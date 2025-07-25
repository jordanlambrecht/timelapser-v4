// src/app/page.tsx
"use client"

import { useState, useEffect, useMemo, memo, useCallback, useRef } from "react"
import { Button } from "@/components/ui/button"
import {
  Plus,
  Camera as CameraIcon,
  Video as VideoIcon,
  Clock,
  Activity,
  Zap,
  Eye,
  Play,
  Pause,
  Square,
  Shield,
} from "lucide-react"
import CameraCard from "@/components/camera-card"
import { StatsCard } from "@/components/stats-card"
import { CameraModal } from "@/components/camera-modal"
import { SpirographLogo } from "@/components/spirograph-logo"
import {
  DeleteCameraConfirmationDialog,
  StopAllTimelapsesConfirmationDialog,
} from "@/components/ui/confirmation-dialog"
import { toast } from "@/lib/toast"
import {
  pauseTimelapse,
  resumeTimelapse,
  stopTimelapse,
  startTimelapse,
} from "@/lib/camera-actions"
import { useDashboardSSE } from "@/hooks/use-camera-sse"
import { useSSE, useSSESubscription } from "@/contexts/sse-context"
import { useSettings } from "@/contexts/settings-context"
import {
  TimelapseCreationModal,
  type TimelapseForm,
} from "@/components/timelapse-creation"
import {
  CorruptionHealthSummary,
  CorruptionAlert,
} from "@/components/corruption-indicator"
import {
  useCorruptionStats,
  useCorruptionActions,
} from "@/hooks/use-corruption-stats"
import type { Camera, Timelapse, Video } from "@/types"
import { cn } from "@/lib/utils"

export default function Dashboard() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [timelapses, setTimelapses] = useState<Timelapse[]>([])
  const [videos, setVideos] = useState<Video[]>([])
  const [dashboardStats, setDashboardStats] = useState<any>(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingCamera, setEditingCamera] = useState<Camera | undefined>()
  const [loading, setLoading] = useState(true)
  const [sseConnected, setSseConnected] = useState(false)
  const [lastEventTime, setLastEventTime] = useState<number>(Date.now())

  // Get temperature unit from settings
  const { temperatureUnit } = useSettings()

  // Confirmation dialog state
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false)
  const [cameraToDelete, setCameraToDelete] = useState<Camera | null>(null)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [stopAllConfirmOpen, setStopAllConfirmOpen] = useState(false)
  const [bulkOperationLoading, setBulkOperationLoading] = useState<
    string | null
  >(null)

  // New timelapse creation modal state
  const [newTimelapseModalOpen, setNewTimelapseModalOpen] = useState(false)

  // Phase 3: Corruption detection integration
  const { systemStats: corruptionStats, loading: corruptionLoading } =
    useCorruptionStats()
  const { resetCameraDegradedMode } = useCorruptionActions()

  // Optimized data fetching - using unified dashboard endpoint for stats
  const fetchData = async () => {
    try {
      // Fetch dashboard statistics and entity data in parallel
      const [dashboardRes, camerasRes, timelapsesRes, videosRes] =
        await Promise.all([
          fetch("/api/dashboard"),
          fetch("/api/cameras"),
          fetch("/api/timelapses"),
          fetch("/api/videos"),
        ])

      // Handle dashboard statistics
      if (dashboardRes.ok) {
        const dashboardData = await dashboardRes.json()
        setDashboardStats(dashboardData)
      } else {
        console.error("Failed to fetch dashboard stats:", dashboardRes.status)
      }

      // Handle entity data
      const camerasData = await camerasRes.json()
      const timelapsesData = await timelapsesRes.json()
      const videosData = await videosRes.json()

      setCameras(Array.isArray(camerasData) ? camerasData : [])
      setTimelapses(Array.isArray(timelapsesData) ? timelapsesData : [])
      setVideos(Array.isArray(videosData) ? videosData : [])
    } catch (error) {
      console.error("Error fetching dashboard data:", error)
    } finally {
      setLoading(false)
    }
  }

  // Real-time updates via centralized SSE
  useDashboardSSE({
    onCameraAdded: (data) => {
      setCameras((prev) => [data.camera, ...prev])
    },
    onCameraDeleted: (data) => {
      setCameras((prev) =>
        prev.filter((camera) => camera.id !== data.camera_id)
      )
      setTimelapses((prev) =>
        prev.filter((t) => t.camera_id !== data.camera_id)
      )
      setVideos((prev) => prev.filter((v) => v.camera_id !== data.camera_id))
    },
    onVideoGenerated: (data) => {
      if (data.video) {
        setVideos((prev) => [data.video, ...prev])
      }
    },
  })

  // Global SSE connection for dashboard-wide events
  const { isConnected } = useSSE()

  // Subscribe to specific dashboard events including corruption events
  useSSESubscription(
    (event) =>
      [
        "camera_updated",
        "camera_deleted",
        "timelapse_status_changed",
        "image_captured",
        "image_corruption_detected",
        "camera_degraded_mode_triggered",
        "camera_corruption_reset",
        "corruption_stats_updated",
        "weather_updated",
      ].includes(event.type),
    (event) => {
      setLastEventTime(Date.now())

      switch (event.type) {
        case "camera_updated":
          setCameras((prev) =>
            prev.map((camera) =>
              camera.id === event.data.camera_id
                ? { ...camera, ...event.data.camera }
                : camera
            )
          )
          break

        case "timelapse_status_changed":
          console.log(
            "[Dashboard SSE] Received timelapse_status_changed event:",
            event.data
          )
          setTimelapses((prev) => {
            console.log(
              "[Dashboard SSE] Current timelapses before update:",
              prev
            )
            const updated = prev.map((timelapse) =>
              timelapse.camera_id === event.data.camera_id
                ? {
                    ...timelapse,
                    status: event.data.status,
                    id: event.data.timelapse_id || timelapse.id,
                  }
                : timelapse
            )

            // If no existing timelapse for this camera, create one
            const hasExisting = prev.some(
              (t) => t.camera_id === event.data.camera_id
            )
            if (!hasExisting && event.data.timelapse_id) {
              return [
                ...updated,
                {
                  id: event.data.timelapse_id,
                  camera_id: event.data.camera_id,
                  status: event.data.status,
                  image_count: 0,
                  last_capture_at: undefined,
                  // Required fields for Timelapse type
                  time_window_type: "none" as const,
                  use_custom_time_window: false,
                  created_at: new Date().toISOString(),
                  updated_at: new Date().toISOString(),
                },
              ]
            }

            console.log(
              "[Dashboard SSE] Updated timelapses after processing:",
              updated
            )
            return updated
          })
          break

        case "image_captured":
          // Update image count for timelapse
          setTimelapses((prev) =>
            prev.map((timelapse) =>
              timelapse.camera_id === event.data.camera_id
                ? {
                    ...timelapse,
                    image_count:
                      event.data.image_count || timelapse.image_count,
                  }
                : timelapse
            )
          )

          // Show toast notification for image capture
          const camera = cameras.find((c) => c.id === event.data.camera_id)
          if (camera) {
            toast.imageCaptured(camera.name)
          }

          // Note: Removed redundant API call that was causing performance issues.
          // Camera data updates should come through dedicated SSE events.
          break

        case "image_corruption_detected":
          // Show toast notification for corruption detection
          if (event.data.is_corrupted && event.data.corruption_score < 50) {
            toast.warning(
              `Camera ${event.data.camera_id}: Poor image quality detected (Score: ${event.data.corruption_score})`
            )
          }
          break

        case "camera_degraded_mode_triggered":
          // Update camera with degraded mode status and show alert
          setCameras((prev) =>
            prev.map((camera) =>
              camera.id === event.data.camera_id
                ? {
                    ...camera,
                    degraded_mode_active: true,
                    consecutive_corruption_failures:
                      event.data.consecutive_failures || 0,
                  }
                : camera
            )
          )
          toast.error(
            `Camera ${event.data.camera_id} entered degraded mode due to quality issues`
          )
          break

        case "camera_corruption_reset":
          // Update camera status and show success toast
          setCameras((prev) =>
            prev.map((camera) =>
              camera.id === event.data.camera_id
                ? {
                    ...camera,
                    degraded_mode_active: false,
                    consecutive_corruption_failures: 0,
                  }
                : camera
            )
          )
          if (!event.data.error) {
            toast.success(
              `Camera ${event.data.cameraId} degraded mode reset successfully`
            )
          } else {
            toast.error(
              `Failed to reset camera ${event.data.cameraId}: ${event.data.error}`
            )
          }
          break

        case "camera_deleted":
          // Remove the deleted camera from the state
          setCameras((prev) =>
            prev.filter((camera) => camera.id !== event.data.camera_id)
          )
          // Also remove any timelapses associated with this camera
          setTimelapses((prev) =>
            prev.filter(
              (timelapse) => timelapse.camera_id !== event.data.camera_id
            )
          )
          console.log(
            "[Dashboard SSE] Camera deleted:",
            event.data.camera_id,
            event.data.camera_name
          )
          break

        case "corruption_stats_updated":
          // Refresh corruption stats when updated
          // The useCorruptionStats hook will handle the refetch automatically
          break

        case "weather_updated":
          // Show toast notification for weather updates
          toast.weatherUpdated(
            event.data.temperature,
            event.data.description,
            temperatureUnit
          )
          break
      }
    }
  )

  // Update SSE connection state
  useEffect(() => {
    setSseConnected(isConnected)
  }, [isConnected])

  useEffect(() => {
    // Initial data fetch only - no more polling!
    fetchData()
  }, [])

  const handleSaveCamera = async (cameraData: any) => {
    try {
      const url = editingCamera
        ? `/api/cameras/${editingCamera.id}`
        : "/api/cameras"
      const method = editingCamera ? "PUT" : "POST"

      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cameraData),
      })

      if (response.ok) {
        setIsModalOpen(false)

        // Show appropriate toast
        if (editingCamera) {
          toast.cameraRenamed(editingCamera.name, cameraData.name)
        } else {
          toast.cameraAdded(cameraData.name)
        }

        setEditingCamera(undefined)

        // If SSE is not connected or hasn't received events recently, refresh data
        if (!sseConnected || Date.now() - lastEventTime > 10000) {
          // SSE not reliable, refreshing data manually
          setTimeout(() => fetchData(), 1000) // Refresh after 1 second
        }
      } else {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
    } catch (error) {
      console.error("Error saving camera:", error)
      toast.error(
        editingCamera ? "Failed to update camera" : "Failed to add camera",
        {
          description: "Please check your settings and try again",
        }
      )
      // Keep modal open on error so user can retry
    }
  }

  const handleToggleTimelapse = async (
    cameraId: number,
    currentStatus: string
  ) => {
    try {
      const camera = cameras.find((c) => c.id === cameraId)
      const timelapse = timelapses.find((t) => t.camera_id === cameraId)

      console.log("handleToggleTimelapse called:", {
        cameraId,
        currentStatus,
        timelapse: timelapse
          ? { id: timelapse.id, status: timelapse.status }
          : null,
      })

      if (currentStatus === "running" && timelapse) {
        // Stop the timelapse using new unified endpoint
        console.log("Attempting to stop timelapse for camera:", cameraId)
        const result = await stopTimelapse(cameraId)

        if (result.success && camera) {
          console.log("Timelapse completed successfully")
          toast.timelapseStopped(camera.name, async () => {
            // Undo action - restart a new timelapse using new unified endpoint
            try {
              const restartResult = await startTimelapse(cameraId, {
                name: timelapse.name || `${camera.name} Timelapse`,
              })

              if (restartResult.success) {
                toast.timelapseStarted(camera.name)
                // SSE event will handle state update automatically
              } else {
                throw new Error(
                  restartResult.message || "Failed to restart timelapse"
                )
              }
            } catch (error) {
              console.error("Failed to restart timelapse:", error)
              toast.error("Failed to restart timelapse", {
                description: "You may need to start it manually",
              })
            }
          })
        } else {
          console.error("Failed to complete timelapse:", result.message)
          throw new Error(result.message || "Failed to stop timelapse")
        }
      } else {
        console.warn("Stop condition not met:", {
          currentStatus,
          hasTimelapse: !!timelapse,
          timelapseId: timelapse?.id,
          timelapseStatus: timelapse?.status,
        })

        if (!timelapse) {
          toast.error("No active timelapse found to stop")
          return
        }

        if (currentStatus !== "running") {
          toast.error("Timelapse is not currently running")
          return
        }
      }

      // If SSE is not connected or hasn't received events recently, refresh data
      if (!sseConnected || Date.now() - lastEventTime > 10000) {
        // SSE not reliable, refreshing data manually
        setTimeout(() => fetchData(), 1000) // Refresh after 1 second
      }
    } catch (error) {
      console.error("Error toggling timelapse:", error)
      toast.error("Failed to toggle timelapse", {
        description: "Please try again",
      })
    }
  }

  const handlePauseTimelapse = async (cameraId: number) => {
    try {
      const camera = cameras.find((c) => c.id === cameraId)
      const timelapse = timelapses.find((t) => t.camera_id === cameraId)

      if (!timelapse) {
        toast.error("No active timelapse found to pause")
        return
      }

      const result = await pauseTimelapse(cameraId)

      if (result.success && camera) {
        toast.timelapsePaused(camera.name)

        // If SSE is not connected or hasn't received events recently, refresh data
        if (!sseConnected || Date.now() - lastEventTime > 10000) {
          // SSE not reliable, refreshing data manually
          setTimeout(() => fetchData(), 1000) // Refresh after 1 second
        }
      } else {
        throw new Error(result.message || "Failed to pause timelapse")
      }
    } catch (error) {
      console.error("Error pausing timelapse:", error)
      toast.error("Failed to pause timelapse", {
        description: "Please try again",
      })
    }
  }

  const handleResumeTimelapse = async (cameraId: number) => {
    try {
      const camera = cameras.find((c) => c.id === cameraId)
      const timelapse = timelapses.find((t) => t.camera_id === cameraId)

      if (!timelapse) {
        toast.error("No timelapse found to resume")
        return
      }

      const result = await resumeTimelapse(cameraId)

      if (result.success && camera) {
        toast.timelapseResumed(camera.name)

        // If SSE is not connected or hasn't received events recently, refresh data
        if (!sseConnected || Date.now() - lastEventTime > 10000) {
          // SSE not reliable, refreshing data manually
          setTimeout(() => fetchData(), 1000) // Refresh after 1 second
        }
      } else {
        throw new Error(result.message || "Failed to resume timelapse")
      }
    } catch (error) {
      console.error("Error resuming timelapse:", error)
      toast.error("Failed to resume timelapse", {
        description: "Please try again",
      })
    }
  }

  const handleDeleteCamera = useCallback(
    async (cameraId: number) => {
      const camera = cameras.find((c) => c.id === cameraId)
      if (!camera) return

      setCameraToDelete(camera)
      setConfirmDeleteOpen(true)
    },
    [cameras]
  )

  const confirmDeleteCamera = async () => {
    if (!cameraToDelete) return

    setDeleteLoading(true)
    try {
      const response = await fetch(`/api/cameras/${cameraToDelete.id}`, {
        method: "DELETE",
      })

      if (response.ok) {
        // Show success toast with undo functionality
        toast.cameraDeleted(cameraToDelete.name, async () => {
          // Undo action - recreate the camera
          try {
            const recreateResponse = await fetch("/api/cameras", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                name: cameraToDelete.name,
                rtsp_url: cameraToDelete.rtsp_url,
                use_time_window: cameraToDelete.use_time_window,
                time_window_start: cameraToDelete.time_window_start,
                time_window_end: cameraToDelete.time_window_end,
              }),
            })

            if (recreateResponse.ok) {
              toast.success(`Camera "${cameraToDelete.name}" restored`, {
                description: "Camera has been recreated successfully",
              })
              // SSE event will handle state update automatically
            } else {
              throw new Error("Failed to restore camera")
            }
          } catch (error) {
            console.error("Failed to restore camera:", error)
            toast.error("Failed to restore camera", {
              description: "You may need to recreate it manually",
            })
          }
        })

        // SSE events will handle updating the state automatically
        setConfirmDeleteOpen(false)
        setCameraToDelete(null)
      } else {
        throw new Error("Failed to delete camera")
      }
    } catch (error) {
      console.error("Error deleting camera:", error)
      toast.error("Failed to delete camera", {
        description: "Please try again",
      })
    } finally {
      setDeleteLoading(false)
    }
  }

  const handleGenerateVideo = async (cameraId: number) => {
    try {
      await fetch("/api/videos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ camera_id: cameraId }),
      })
      // SSE events will handle updating the state automatically
    } catch (error) {
      console.error("Error generating video:", error)
    }
  }

  // Bulk timelapse control functions - updated to use new entity-based endpoints
  const handleBulkResume = async () => {
    setBulkOperationLoading("resume")

    const pausedCameras = cameras.filter((camera) => {
      const timelapse = timelapses.find((t) => t.camera_id === camera.id)
      return (
        camera.health_status === "online" &&
        timelapse &&
        timelapse.status === "paused"
      )
    })

    if (pausedCameras.length === 0) {
      toast.info("No cameras available to resume", {
        description: "All cameras are already running or stopped",
      })
      setBulkOperationLoading(null)
      return
    }

    let successCount = 0
    let failCount = 0

    // Process cameras in parallel using entity-based endpoints
    const promises = pausedCameras.map(async (camera) => {
      try {
        const timelapse = timelapses.find((t) => t.camera_id === camera.id)
        if (!timelapse) {
          failCount++
          return
        }

        const result = await resumeTimelapse(camera.id)

        if (result.success) {
          successCount++
        } else {
          failCount++
        }
      } catch (error) {
        console.error(
          `Failed to resume timelapse for camera ${camera.name}:`,
          error
        )
        failCount++
      }
    })

    await Promise.all(promises)

    if (successCount > 0) {
      toast.success(
        `Resumed ${successCount} timelapse${successCount > 1 ? "s" : ""}`,
        {
          description:
            failCount > 0
              ? `${failCount} failed to resume`
              : "All paused timelapses are now recording",
        }
      )
    } else {
      toast.error("Failed to resume any timelapses", {
        description: "Please check individual cameras and try again",
      })
    }

    setBulkOperationLoading(null)
  }

  const handleBulkPause = async () => {
    setBulkOperationLoading("pause")

    const runningCameras = cameras.filter((camera) => {
      const timelapse = timelapses.find((t) => t.camera_id === camera.id)
      return (
        camera.health_status === "online" &&
        timelapse &&
        timelapse.status === "running"
      )
    })

    if (runningCameras.length === 0) {
      toast.info("No running timelapses to pause", {
        description: "All cameras are either stopped or already paused",
      })
      setBulkOperationLoading(null)
      return
    }

    let successCount = 0
    let failCount = 0

    // Process cameras in parallel using entity-based endpoints
    const promises = runningCameras.map(async (camera) => {
      try {
        const timelapse = timelapses.find((t) => t.camera_id === camera.id)
        if (!timelapse) {
          failCount++
          return
        }

        const result = await pauseTimelapse(camera.id)

        if (result.success) {
          successCount++
        } else {
          failCount++
        }
      } catch (error) {
        console.error(
          `Failed to pause timelapse for camera ${camera.name}:`,
          error
        )
        failCount++
      }
    })

    await Promise.all(promises)

    if (successCount > 0) {
      toast.success(
        `Paused ${successCount} timelapse${successCount > 1 ? "s" : ""}`,
        {
          description:
            failCount > 0
              ? `${failCount} failed to pause`
              : "Recording paused for all running cameras",
        }
      )
    } else {
      toast.error("Failed to pause any timelapses", {
        description: "Please check individual cameras and try again",
      })
    }

    setBulkOperationLoading(null)
  }

  const handleBulkStop = async () => {
    setBulkOperationLoading("stop")

    const activeCameras = cameras.filter((camera) => {
      const timelapse = timelapses.find((t) => t.camera_id === camera.id)
      return (
        camera.health_status === "online" &&
        timelapse &&
        (timelapse.status === "running" || timelapse.status === "paused")
      )
    })

    if (activeCameras.length === 0) {
      toast.info("No active timelapses to stop", {
        description: "All cameras are already stopped",
      })
      setBulkOperationLoading(null)
      return
    }

    let successCount = 0
    let failCount = 0
    const stoppedCameras: Camera[] = []

    // Process cameras in parallel using entity-based endpoints
    const promises = activeCameras.map(async (camera) => {
      try {
        const timelapse = timelapses.find((t) => t.camera_id === camera.id)
        if (!timelapse) {
          failCount++
          return
        }

        // Stop the timelapse using new unified endpoint
        const result = await stopTimelapse(camera.id)

        if (result.success) {
          successCount++
          stoppedCameras.push(camera)
        } else {
          failCount++
        }
      } catch (error) {
        console.error(
          `Failed to stop timelapse for camera ${camera.name}:`,
          error
        )
        failCount++
      }
    })

    await Promise.all(promises)

    if (successCount > 0) {
      toast.successWithUndo(
        `Stopped ${successCount} timelapse${successCount > 1 ? "s" : ""}`,
        {
          description:
            failCount > 0
              ? `${failCount} failed to stop`
              : "All active recordings have been stopped",
          undoAction: async () => {
            // Restart all stopped cameras with new timelapses using new unified endpoint
            const restartPromises = stoppedCameras.map(async (camera) => {
              try {
                await startTimelapse(camera.id, {
                  name: `${camera.name} Timelapse`,
                })
              } catch (error) {
                console.error(
                  `Failed to restart timelapse for camera ${camera.name}:`,
                  error
                )
              }
            })

            await Promise.all(restartPromises)
            toast.success(
              `Restarted ${stoppedCameras.length} timelapse${
                stoppedCameras.length > 1 ? "s" : ""
              }`,
              {
                description: "All timelapses have been restarted",
              }
            )
          },
          undoTimeout: 10000,
        }
      )
    } else {
      toast.error("Failed to stop any timelapses", {
        description: "Please check individual cameras and try again",
      })
    }

    setBulkOperationLoading(null)
  }

  const handleStopAllWithConfirmation = () => {
    setStopAllConfirmOpen(true)
  }

  const confirmStopAll = async () => {
    setStopAllConfirmOpen(false)
    await handleBulkStop()
  }

  // ✅ PERFORMANCE OPTIMIZATION: Memoized camera list with timelapse/video mapping
  const memoizedCameraList = useMemo(() => {
    return cameras.map((camera) => {
      const timelapse = timelapses.find((t) => t.camera_id === camera.id)
      const cameraVideos = videos.filter((v) => v.camera_id === camera.id)

      return {
        camera,
        timelapse,
        cameraVideos,
      }
    })
  }, [cameras, timelapses, videos])

  // ✅ PERFORMANCE OPTIMIZATION: Memoized event handlers to prevent prop drilling re-renders
  const handleEditCamera = useCallback(
    (id: number) => {
      const cam = cameras.find((c) => c.id === id)
      setEditingCamera(cam)
      setIsModalOpen(true)
    },
    [cameras]
  )

  const handleDeleteCameraCallback = useCallback(
    (cameraId: number) => {
      handleDeleteCamera(cameraId)
    },
    [handleDeleteCamera]
  )

  // Use dashboard statistics if available, otherwise calculate from local data
  const onlineCameras = cameras.filter(
    (c) => c.health_status === "online"
  ).length
  const activTimelapses =
    dashboardStats?.timelapse?.running_timelapses ??
    timelapses.filter((t) => t.status === "running").length
  const pausedTimelapses =
    dashboardStats?.timelapse?.paused_timelapses ??
    timelapses.filter((t) => t.status === "paused").length
  const totalVideos =
    dashboardStats?.video?.completed_videos ??
    videos.filter((v) => v.status === "completed").length
  const totalImages =
    dashboardStats?.image?.total_images ??
    timelapses.reduce((sum, t) => sum + (t.image_count || 0), 0)

  const handleCorruptionReset = async (cameraId: number) => {
    try {
      await resetCameraDegradedMode(cameraId)
      // SSE events will handle camera status updates automatically
    } catch (error) {
      console.error("Failed to reset camera degraded mode:", error)
    }
  }

  // Handle timelapse creation
  const handleTimelapseSubmit = async (
    form: TimelapseForm,
    cameraId?: number
  ) => {
    try {
      console.log("Creating timelapse with form:", form)

      // Use provided cameraId or find the first active camera
      let targetCamera
      if (cameraId) {
        targetCamera = cameras.find((camera) => camera.id === cameraId)
        if (!targetCamera) {
          toast.error(`Camera with ID ${cameraId} not found`)
          return
        }
      } else {
        targetCamera = cameras.find((camera) => camera.status === "active")
        if (!targetCamera) {
          toast.error("No active camera found. Please activate a camera first.")
          return
        }
      }

      // Convert TimelapseForm to backend API format
      const timelapseData = {
        name:
          form.name ||
          `Timelapse ${new Date()
            .toISOString()
            .slice(0, 19)
            .replace("T", " ")}`,
        capture_interval_seconds: form.captureInterval,

        // Time window settings
        time_window_type: form.runWindowEnabled
          ? form.runWindowType === "sunrise-sunset"
            ? "sunrise_sunset"
            : "time"
          : "none",
        time_window_start:
          form.runWindowEnabled && form.runWindowType === "between"
            ? form.timeWindowStart
            : null,
        time_window_end:
          form.runWindowEnabled && form.runWindowType === "between"
            ? form.timeWindowEnd
            : null,
        sunrise_offset_minutes:
          form.runWindowEnabled && form.runWindowType === "sunrise-sunset"
            ? form.sunriseOffsetMinutes
            : null,
        sunset_offset_minutes:
          form.runWindowEnabled && form.runWindowType === "sunrise-sunset"
            ? form.sunsetOffsetMinutes
            : null,
        use_custom_time_window: form.runWindowEnabled,

        // Stop time settings
        auto_stop_at:
          form.stopTimeEnabled && form.stopType === "datetime"
            ? form.stopDateTime
            : null,

        // Video generation settings
        video_generation_mode: form.videoGenerationMode,
        standard_fps: form.videoStandardFps,
        enable_time_limits: form.videoEnableTimeLimits,
        min_time_seconds: form.videoEnableTimeLimits
          ? form.videoMinDuration * 60
          : null,
        max_time_seconds: form.videoEnableTimeLimits
          ? form.videoMaxDuration * 60
          : null,
        target_time_seconds:
          form.videoGenerationMode === "target"
            ? form.videoTargetDuration * 60
            : null,
        fps_bounds_min: form.videoFpsMin,
        fps_bounds_max: form.videoFpsMax,

        // Video automation settings
        video_automation_mode: form.videoManualOnly
          ? "manual"
          : form.videoPerCapture
          ? "per_capture"
          : form.videoScheduled
          ? "scheduled"
          : form.videoMilestone
          ? "milestone"
          : "manual",

        // Generation schedule (for scheduled automation)
        generation_schedule: form.videoScheduled
          ? {
              type: form.videoScheduleType,
              time: form.videoScheduleTime,
              enabled: true,
              timezone: "UTC", // TODO: Get from settings
            }
          : null,

        // Milestone config (for milestone automation)
        milestone_config: form.videoMilestone
          ? {
              thresholds: [form.videoMilestoneInterval],
              enabled: true,
              reset_on_completion: !form.videoMilestoneOverwrite,
            }
          : null,
      }

      // Call the camera timelapse action API to create and start the timelapse
      const response = await fetch(
        `/api/cameras/${targetCamera.id}/timelapse-action`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            action: "create",
            timelapse_data: timelapseData,
          }),
        }
      )

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(
          errorData.detail ||
            `HTTP ${response.status}: Failed to create timelapse`
        )
      }

      const newTimelapse = await response.json()

      // Refresh the data to show the new timelapse
      await fetchData()

      toast.success(
        `Timelapse "${
          newTimelapse.name || newTimelapse.id
        }" created successfully!`
      )
    } catch (error) {
      console.error("Failed to create timelapse:", error)
      toast.error(
        error instanceof Error ? error.message : "Failed to create timelapse"
      )
    }
  }

  if (loading) {
    return (
      <div className='flex items-center justify-center min-h-[60vh]'>
        <div className='space-y-6 text-center'>
          <div className='relative'>
            <div className='w-16 h-16 mx-auto border-4 rounded-full border-pink/20 border-t-pink animate-spin' />
            <div
              className='absolute inset-0 w-16 h-16 mx-auto border-4 rounded-full border-cyan/20 border-b-cyan animate-spin'
              style={{
                animationDirection: "reverse",
                animationDuration: "1.5s",
              }}
            />
          </div>
          <div>
            <p className='font-medium text-white'>Loading dashboard...</p>
            <p className='mt-1 text-sm text-grey-light/60'>
              Fetching camera data
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className='relative space-y-12'>
      {/* Hero Section with Asymmetric Layout */}
      <div className='relative'>
        {/* animate-float accent elements */}
        <div className='absolute w-2 h-2 rounded-full -top-4 right-1/4 bg-yellow/60 animate-float' />
        <div
          className='absolute w-1 h-12 rounded-full top-8 left-1/3 bg-purple/30 animate-float'
          style={{ animationDelay: "1s" }}
        />

        <div className='grid items-end gap-8 lg:grid-cols-3'>
          <div className='space-y-6 lg:col-span-2'>
            <div className='space-y-4'>
              <div className='flex items-center space-x-4'>
                <SpirographLogo size={64} />
                <h1 className='text-6xl font-bold leading-tight gradient-text'>
                  Control Center
                </h1>
              </div>
              <p className='max-w-2xl text-lg text-grey-light/70'>
                Monitor your RTSP cameras, manage timelapses, and create
                stunning videos with professional-grade automation tools.
              </p>
            </div>
          </div>

          <div className='flex justify-end'>
            <Button
              onClick={() => setIsModalOpen(true)}
              size='lg'
              className='px-8 py-4 text-lg font-bold text-black transition-all duration-300 bg-gradient-to-r from-pink to-cyan hover:from-pink-dark hover:to-cyan rounded-2xl hover:shadow-2xl hover:shadow-pink/20 hover:scale-105'
            >
              <Plus className='w-6 h-6 mr-3' />
              Add Camera
            </Button>
          </div>
        </div>
      </div>

      {/* New Timelapse Button */}
      <div className='flex justify-center mb-8'>
        <Button
          onClick={() => setNewTimelapseModalOpen(true)}
          size='lg'
          className='bg-gradient-to-r from-purple to-cyan hover:from-purple/80 hover:to-cyan/80 text-white font-medium'
        >
          <Plus className='w-5 h-5 mr-2' />
          Create New Timelapse
        </Button>
      </div>

      {/* Stats Grid with Creative Layout */}
      <div className='grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4'>
        <StatsCard
          title='Total Cameras'
          value={dashboardStats?.camera?.total_cameras ?? cameras.length}
          description={`${onlineCameras} online`}
          icon={CameraIcon}
          color='cyan'
          trend={
            onlineCameras > 0 &&
            (dashboardStats?.camera?.total_cameras ?? cameras.length) > 0
              ? {
                  value: Math.round(
                    (onlineCameras /
                      (dashboardStats?.camera?.total_cameras ??
                        cameras.length)) *
                      100
                  ),
                  label: "uptime",
                }
              : undefined
          }
        />
        <StatsCard
          title='Active Recordings'
          value={activTimelapses}
          description={
            pausedTimelapses > 0
              ? `${pausedTimelapses} paused`
              : "Currently capturing"
          }
          icon={Activity}
          color='success'
        />
        <StatsCard
          title='Generated Videos'
          value={totalVideos}
          description='Ready to download'
          icon={VideoIcon}
          color='purple'
        />
        <StatsCard
          title='Total Frames'
          value={totalImages.toLocaleString()}
          description='Images captured'
          icon={Zap}
          color='yellow'
        />
      </div>

      {/* Bulk Timelapse Controls */}
      {cameras.length > 0 && (
        <div className='space-y-6'>
          <div className='flex items-center justify-between'>
            <div className='space-y-2'>
              <h3 className='text-xl font-semibold text-white'>
                Bulk Controls
              </h3>
              <p className='text-sm text-grey-light/60'>
                Resume paused timelapses across multiple cameras
              </p>
            </div>
          </div>

          <div className='flex items-center gap-4 p-6 glass rounded-2xl border border-purple-muted/20'>
            <div className='flex items-center space-x-3'>
              <div className='p-2 bg-gradient-to-br from-green-500/20 to-emerald-500/20 rounded-xl'>
                <Play className='w-5 h-5 text-emerald-400' />
              </div>
              <div>
                <span className='text-sm font-medium text-white'>
                  Bulk Resume
                </span>
                <p className='text-xs text-grey-light/60'>
                  Resume all paused timelapses
                </p>
              </div>
            </div>

            <div className='flex items-center gap-3 ml-auto'>
              {(() => {
                const pausedCameras = cameras.filter((camera) => {
                  const timelapse = timelapses.find(
                    (t) => t.camera_id === camera.id
                  )
                  return (
                    camera.health_status === "online" &&
                    timelapse &&
                    timelapse.status === "paused"
                  )
                })
                const canResume = pausedCameras.length > 0

                return (
                  <div className='relative'>
                    <Button
                      onClick={handleBulkResume}
                      size='sm'
                      disabled={!canResume || bulkOperationLoading === "resume"}
                      title={
                        !canResume
                          ? "No cameras can be resumed at the moment"
                          : "Resume all paused timelapses"
                      }
                      className='bg-gradient-to-r from-emerald-500 to-green-500 hover:from-emerald-600 hover:to-green-600 text-white font-medium px-4 py-2 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed'
                    >
                      <Play className='w-4 h-4 mr-2' />
                      {bulkOperationLoading === "resume"
                        ? "Resuming..."
                        : "Resume"}
                    </Button>
                  </div>
                )
              })()}

              <Button
                onClick={handleBulkPause}
                size='sm'
                variant='outline'
                disabled={bulkOperationLoading === "pause"}
                className='border-yellow-500/40 text-yellow-400 hover:bg-yellow-500/10 hover:border-yellow-500/60 font-medium px-4 py-2 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed'
              >
                <Pause className='w-4 h-4 mr-2' />
                {bulkOperationLoading === "pause" ? "Pausing..." : "Pause All"}
              </Button>

              <Button
                onClick={handleStopAllWithConfirmation}
                size='sm'
                variant='outline'
                disabled={bulkOperationLoading === "stop"}
                className='border-red-500/40 text-red-400 hover:bg-red-500/10 hover:border-red-500/60 font-medium px-4 py-2 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed'
              >
                <Square className='w-4 h-4 mr-2' />
                {bulkOperationLoading === "stop" ? "Stopping..." : "Stop All"}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* System Health Overview */}
      <div className='grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4'>
        {/* ...existing health cards... */}

        {/* Phase 3: Corruption Health Summary Card */}
        {!corruptionLoading && corruptionStats && (
          <div className='p-4 bg-purple-800 rounded-lg shadow-md'>
            <div className='flex items-center justify-between mb-2'>
              <h3 className='text-lg font-semibold text-white'>
                Image Quality
              </h3>
              <Shield className='w-6 h-6 text-purple-300' />
            </div>
            <CorruptionHealthSummary
              stats={corruptionStats}
              className='space-y-2'
            />
          </div>
        )}
      </div>

      {/* Phase 3: Corruption Alerts for Degraded Cameras */}
      {cameras
        .filter((camera) => camera.degraded_mode_active)
        .map((camera) => (
          <CorruptionAlert
            key={`corruption-${camera.id}`}
            camera={camera}
            onReset={handleCorruptionReset}
            className='mb-4'
          />
        ))}

      {/* Cameras Section with Dynamic Layout */}
      <div className='space-y-8'>
        <div className='flex items-center justify-between'>
          <div className='space-y-2'>
            <h2 className='text-3xl font-bold text-white'>Camera Network</h2>
            <div className='flex items-center space-x-4 text-sm'>
              {cameras.length > 0 && (
                <>
                  <div className='flex items-center space-x-2'>
                    <div className='w-2 h-2 rounded-full bg-success' />
                    <span className='text-grey-light/70'>
                      {onlineCameras} online
                    </span>
                  </div>
                  <div className='w-1 h-4 rounded-full bg-purple-muted/30' />
                  <div className='flex items-center space-x-2'>
                    <Eye className='w-4 h-4 text-cyan/70' />
                    <span className='text-grey-light/70'>
                      {cameras.length} total
                    </span>
                  </div>
                  <div className='w-1 h-4 rounded-full bg-purple-muted/30' />
                  <div className='flex items-center space-x-2'>
                    <div
                      className={`w-2 h-2 rounded-full ${
                        sseConnected ? "bg-success" : "bg-error"
                      }`}
                    />
                    <span className='text-grey-light/70'>
                      {sseConnected ? "live updates" : "disconnected"}
                    </span>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {cameras.length === 0 ? (
          <div className='relative py-16 text-center'>
            {/* Empty state with creative design */}
            <div className='relative max-w-md mx-auto'>
              <div className='absolute w-4 h-4 rounded-full -top-8 -left-8 bg-pink/40 animate-float' />
              <div
                className='absolute w-2 h-2 rounded-full -top-4 -right-6 bg-cyan/60 animate-float'
                style={{ animationDelay: "1s" }}
              />

              <div className='p-12 border glass-strong rounded-3xl border-purple-muted/30'>
                <div className='flex items-center justify-center w-20 h-20 mx-auto mb-6 bg-gradient-to-br from-purple/20 to-cyan/20 rounded-2xl rotate-12'>
                  <CameraIcon className='w-10 h-10 text-white' />
                </div>

                <h3 className='mb-3 text-2xl font-bold text-white'>
                  No cameras yet
                </h3>
                <p className='mb-8 leading-relaxed text-grey-light/60'>
                  Ready to create your first timelapse? Add an RTSP camera to
                  get started with professional automated video creation.
                </p>

                <Button
                  onClick={() => setIsModalOpen(true)}
                  className='px-8 py-3 font-bold text-black transition-all duration-300 bg-gradient-to-r from-pink to-cyan hover:from-pink-dark hover:to-cyan rounded-xl hover:shadow-xl'
                >
                  <Plus className='w-5 h-5 mr-2' />
                  Add Your First Camera
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <div className='grid grid-cols-1 gap-8 md:grid-cols-2 xl:grid-cols-3'>
            {memoizedCameraList.map(({ camera, timelapse, cameraVideos }) => (
              <CameraCard
                key={camera.id}
                camera={camera}
                timelapse={timelapse}
                videos={cameraVideos}
                onEditCamera={handleEditCamera}
                onDeleteCamera={handleDeleteCameraCallback}
              />
            ))}
          </div>
        )}
      </div>

      {/* Camera Modal */}
      <CameraModal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false)
          setEditingCamera(undefined)
        }}
        onSave={handleSaveCamera}
        camera={editingCamera}
        title={editingCamera ? "Edit Camera" : "Add New Camera"}
      />

      {/* Confirmation Dialog */}
      <DeleteCameraConfirmationDialog
        isOpen={confirmDeleteOpen}
        onClose={() => {
          setConfirmDeleteOpen(false)
          setCameraToDelete(null)
        }}
        onConfirm={confirmDeleteCamera}
        cameraName={cameraToDelete?.name || "Unknown Camera"}
        isLoading={deleteLoading}
      />

      {/* Stop All Confirmation Dialog */}
      <StopAllTimelapsesConfirmationDialog
        isOpen={stopAllConfirmOpen}
        onClose={() => setStopAllConfirmOpen(false)}
        onConfirm={confirmStopAll}
        cameraCount={
          cameras.filter((camera) => {
            const timelapse = timelapses.find((t) => t.camera_id === camera.id)
            return (
              camera.health_status === "online" &&
              timelapse &&
              (timelapse.status === "running" || timelapse.status === "paused")
            )
          }).length
        }
        isLoading={bulkOperationLoading === "stop"}
      />

      {/* New Timelapse Creation Modal */}
      <TimelapseCreationModal
        isOpen={newTimelapseModalOpen}
        onClose={() => setNewTimelapseModalOpen(false)}
        onSubmit={handleTimelapseSubmit}
      />
    </div>
  )
}
