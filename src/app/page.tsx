"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Plus, Camera, Video, Clock, Activity, Zap, Eye } from "lucide-react"
import { CameraCard } from "@/components/camera-card"
import { StatsCard } from "@/components/stats-card"
import { CameraModal } from "@/components/camera-modal"
import { SpirographLogo } from "@/components/spirograph-logo"

interface Camera {
  id: number
  name: string
  rtsp_url: string
  status: string
  health_status: "online" | "offline" | "unknown"
  last_capture_at?: string
  consecutive_failures: number
  time_window_start?: string
  time_window_end?: string
  use_time_window: boolean
  // Full image object instead of just ID
  last_image?: {
    id: number
    captured_at: string
    file_path: string
    file_size: number | null
    day_number: number
  } | null
}

interface Timelapse {
  id: number
  camera_id: number
  status: string
  image_count: number
  last_capture_at?: string
}

interface Video {
  id: number
  camera_id: number
  status: string
  file_size?: number
  duration?: number
  created_at: string
}

export default function Dashboard() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [timelapses, setTimelapses] = useState<Timelapse[]>([])
  const [videos, setVideos] = useState<Video[]>([])
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingCamera, setEditingCamera] = useState<Camera | undefined>()
  const [loading, setLoading] = useState(true)
  const [sseConnected, setSseConnected] = useState(false)
  const [lastEventTime, setLastEventTime] = useState<number>(Date.now())

  const fetchData = async () => {
    try {
      // Use new aggregated dashboard endpoint for better performance
      const response = await fetch("/api/dashboard")

      if (!response.ok) {
        throw new Error(`Dashboard API failed: ${response.status}`)
      }

      const dashboardData = await response.json()

      // Set data from aggregated response
      setCameras(
        Array.isArray(dashboardData.cameras) ? dashboardData.cameras : []
      )
      setTimelapses(
        Array.isArray(dashboardData.timelapses) ? dashboardData.timelapses : []
      )
      setVideos(Array.isArray(dashboardData.videos) ? dashboardData.videos : [])

      // Log performance metadata
      if (dashboardData.metadata) {
        console.log("Dashboard loaded:", dashboardData.metadata)
      }
    } catch (error) {
      console.error("Error fetching dashboard data:", error)

      // Fallback to individual API calls if aggregated endpoint fails
      console.log("Falling back to individual API calls...")
      try {
        const [camerasRes, timelapsesRes, videosRes] = await Promise.all([
          fetch("/api/cameras"),
          fetch("/api/timelapses"),
          fetch("/api/videos"),
        ])

        const camerasData = await camerasRes.json()
        const timelapsesData = await timelapsesRes.json()
        const videosData = await videosRes.json()

        setCameras(Array.isArray(camerasData) ? camerasData : [])
        setTimelapses(Array.isArray(timelapsesData) ? timelapsesData : [])
        setVideos(Array.isArray(videosData) ? videosData : [])
      } catch (fallbackError) {
        console.error("Fallback API calls also failed:", fallbackError)
      }
    } finally {
      setLoading(false)
    }
  }

  // Real-time updates via Server-Sent Events with reconnection logic
  useEffect(() => {
    let eventSource: EventSource | null = null
    let reconnectTimer: NodeJS.Timeout | null = null
    let reconnectAttempts = 0
    const maxReconnectAttempts = 5
    const baseReconnectDelay = 1000 // Start with 1 second

    const connectSSE = () => {
      // Clean up existing connection
      if (eventSource) {
        eventSource.close()
      }

      console.log(`Connecting to SSE... (attempt ${reconnectAttempts + 1})`)
      eventSource = new EventSource("/api/events")

      eventSource.onopen = () => {
        console.log("✅ SSE connected successfully")
        setSseConnected(true)
        reconnectAttempts = 0 // Reset attempts on successful connection
      }

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          setLastEventTime(Date.now()) // Track when we last received an event

          console.log("Dashboard SSE event:", data.type, data)

          switch (data.type) {
            case "camera_added":
              setCameras((prev) => [data.camera, ...prev])
              break

            case "camera_updated":
              setCameras((prev) =>
                prev.map((camera) =>
                  camera.id === data.camera.id
                    ? { ...camera, ...data.camera }
                    : camera
                )
              )
              break

            case "camera_deleted":
              setCameras((prev) =>
                prev.filter((camera) => camera.id !== data.camera_id)
              )
              setTimelapses((prev) =>
                prev.filter((t) => t.camera_id !== data.camera_id)
              )
              setVideos((prev) =>
                prev.filter((v) => v.camera_id !== data.camera_id)
              )
              break

            case "timelapse_status_changed":
              console.log("🔄 Processing timelapse status change:", data)
              setTimelapses((prev) => {
                const updated = prev.map((timelapse) =>
                  timelapse.camera_id === data.camera_id
                    ? {
                        ...timelapse,
                        status: data.status,
                        id: data.timelapse_id || timelapse.id,
                      }
                    : timelapse
                )

                // If no existing timelapse for this camera, create one
                const hasExisting = prev.some(
                  (t) => t.camera_id === data.camera_id
                )
                if (!hasExisting && data.timelapse_id) {
                  return [
                    ...updated,
                    {
                      id: data.timelapse_id,
                      camera_id: data.camera_id,
                      status: data.status,
                      image_count: 0,
                      last_capture_at: undefined,
                    },
                  ]
                }

                return updated
              })
              break

            case "video_completed":
              if (data.video) {
                setVideos((prev) => [data.video, ...prev])
              }
              break

            case "video_failed":
              console.error("Video generation failed:", data.error)
              break

            case "image_captured":
              // Update image count for timelapse
              setTimelapses((prev) =>
                prev.map((timelapse) =>
                  timelapse.camera_id === data.camera_id
                    ? {
                        ...timelapse,
                        image_count: data.image_count || timelapse.image_count,
                      }
                    : timelapse
                )
              )
              break

            case "connected":
              console.log("Connected to dashboard events")
              break

            case "heartbeat":
              // Keep connection alive
              break

            default:
              console.log("Unknown dashboard event:", data.type)
          }
        } catch (error) {
          console.error("Error parsing dashboard SSE event:", error)
        }
      }

      eventSource.onerror = (error) => {
        console.error("Dashboard SSE connection error:", error)
        setSseConnected(false)

        // Attempt to reconnect with exponential backoff
        if (reconnectAttempts < maxReconnectAttempts) {
          const delay = baseReconnectDelay * Math.pow(2, reconnectAttempts)
          console.log(
            `Attempting to reconnect SSE in ${delay}ms... (${
              reconnectAttempts + 1
            }/${maxReconnectAttempts})`
          )

          reconnectAttempts++
          reconnectTimer = setTimeout(() => {
            connectSSE()
          }, delay)
        } else {
          console.error(
            "Max SSE reconnection attempts reached. Please refresh the page."
          )
        }
      }
    }

    // Initial connection
    connectSSE()

    // Cleanup on unmount
    return () => {
      if (eventSource) {
        eventSource.close()
      }
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
      }
    }
  }, [])

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
        setEditingCamera(undefined)

        // If SSE is not connected or hasn't received events recently, refresh data
        if (!sseConnected || Date.now() - lastEventTime > 10000) {
          console.log("⚠️ SSE not reliable, refreshing data manually")
          setTimeout(() => fetchData(), 1000) // Refresh after 1 second
        }
      } else {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
    } catch (error) {
      console.error("Error saving camera:", error)
      // Keep modal open on error so user can retry
    }
  }

  const handleToggleTimelapse = async (
    cameraId: number,
    currentStatus: string
  ) => {
    try {
      const newStatus = currentStatus === "running" ? "stopped" : "running"
      const response = await fetch("/api/timelapses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ camera_id: cameraId, status: newStatus }),
      })

      if (response.ok) {
        // If SSE is not connected or hasn't received events recently, refresh data
        if (!sseConnected || Date.now() - lastEventTime > 10000) {
          console.log("⚠️ SSE not reliable, refreshing data manually")
          setTimeout(() => fetchData(), 1000) // Refresh after 1 second
        }
      }
    } catch (error) {
      console.error("Error toggling timelapse:", error)
    }
  }

  const handlePauseTimelapse = async (cameraId: number) => {
    try {
      const response = await fetch("/api/timelapses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ camera_id: cameraId, status: "paused" }),
      })

      if (response.ok) {
        // If SSE is not connected or hasn't received events recently, refresh data
        if (!sseConnected || Date.now() - lastEventTime > 10000) {
          console.log("⚠️ SSE not reliable, refreshing data manually")
          setTimeout(() => fetchData(), 1000) // Refresh after 1 second
        }
      }
    } catch (error) {
      console.error("Error pausing timelapse:", error)
    }
  }

  const handleResumeTimelapse = async (cameraId: number) => {
    try {
      const response = await fetch("/api/timelapses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ camera_id: cameraId, status: "running" }),
      })

      if (response.ok) {
        // If SSE is not connected or hasn't received events recently, refresh data
        if (!sseConnected || Date.now() - lastEventTime > 10000) {
          console.log("⚠️ SSE not reliable, refreshing data manually")
          setTimeout(() => fetchData(), 1000) // Refresh after 1 second
        }
      }
    } catch (error) {
      console.error("Error resuming timelapse:", error)
    }
  }

  const handleDeleteCamera = async (cameraId: number) => {
    if (confirm("Are you sure you want to delete this camera?")) {
      try {
        await fetch(`/api/cameras/${cameraId}`, { method: "DELETE" })
        // SSE events will handle updating the state automatically
      } catch (error) {
        console.error("Error deleting camera:", error)
      }
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

  // Calculate stats
  const onlineCameras = cameras.filter(
    (c) => c.health_status === "online"
  ).length
  const activTimelapses = timelapses.filter(
    (t) => t.status === "running"
  ).length
  const pausedTimelapses = timelapses.filter(
    (t) => t.status === "paused"
  ).length
  const totalVideos = videos.filter((v) => v.status === "completed").length
  const totalImages = timelapses.reduce(
    (sum, t) => sum + (t.image_count || 0),
    0
  )

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
        {/* Floating accent elements */}
        <div className='absolute w-2 h-2 rounded-full -top-4 right-1/4 bg-yellow/60 floating' />
        <div
          className='absolute w-1 h-12 rounded-full top-8 left-1/3 bg-purple/30 floating'
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

      {/* Stats Grid with Creative Layout */}
      <div className='grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4'>
        <StatsCard
          title='Total Cameras'
          value={cameras.length}
          description={`${onlineCameras} online`}
          icon={Camera}
          color='cyan'
          trend={
            onlineCameras > 0
              ? {
                  value: Math.round((onlineCameras / cameras.length) * 100),
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
          icon={Video}
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
              <div className='absolute w-4 h-4 rounded-full -top-8 -left-8 bg-pink/40 floating' />
              <div
                className='absolute w-2 h-2 rounded-full -top-4 -right-6 bg-cyan/60 floating'
                style={{ animationDelay: "1s" }}
              />

              <div className='p-12 border glass-strong rounded-3xl border-purple-muted/30'>
                <div className='flex items-center justify-center w-20 h-20 mx-auto mb-6 bg-gradient-to-br from-purple/20 to-cyan/20 rounded-2xl rotate-12'>
                  <Camera className='w-10 h-10 text-white' />
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
            {cameras.map((camera) => {
              const timelapse = timelapses.find(
                (t) => t.camera_id === camera.id
              )
              const cameraVideos = videos.filter(
                (v) => v.camera_id === camera.id
              )

              return (
                <CameraCard
                  key={camera.id}
                  camera={camera}
                  timelapse={timelapse}
                  videos={cameraVideos}
                  onToggleTimelapse={handleToggleTimelapse}
                  onPauseTimelapse={handlePauseTimelapse}
                  onResumeTimelapse={handleResumeTimelapse}
                  onEditCamera={(id) => {
                    const cam = cameras.find((c) => c.id === id)
                    setEditingCamera(cam)
                    setIsModalOpen(true)
                  }}
                  onDeleteCamera={handleDeleteCamera}
                  onGenerateVideo={handleGenerateVideo}
                />
              )
            })}
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
    </div>
  )
}
