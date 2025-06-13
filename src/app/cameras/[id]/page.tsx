"use client"

import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"

interface Camera {
  id: number
  name: string
  rtsp_url: string
  status: string
  health_status: string
  last_capture_at: string | null
  consecutive_failures: number
  use_time_window: boolean
  time_window_start: string | null
  time_window_end: string | null
}

interface Timelapse {
  id: number
  camera_id: number
  status: string
  start_date: string
  image_count: number
  last_capture_at: string | null
  created_at: string
}

interface Image {
  id: number
  camera_id: number
  timelapse_id: number
  file_path: string
  captured_at: string
  day_number: number
  file_size: number
}

interface CameraDetails {
  camera: Camera
  activeTimelapse: Timelapse | null
  latestImage: Image | null
  stats: {
    currentTimelapseImages: number
    totalImages: number
    videoCount: number
    daysSinceFirstCapture: number
  }
  recentLogs: Array<{
    id: number
    level: string
    message: string
    timestamp: string
  }>
}

export default function CameraDetailsPage() {
  const params = useParams()
  const router = useRouter()
  const cameraId = parseInt(params.id as string)

  const [details, setDetails] = useState<CameraDetails | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  useEffect(() => {
    fetchCameraDetails()
  }, [cameraId])

  const fetchCameraDetails = async () => {
    try {
      const response = await fetch(`/api/cameras/${cameraId}`)
      if (!response.ok) {
        throw new Error("Camera not found")
      }
      const data = await response.json()
      setDetails(data)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch camera details"
      )
    } finally {
      setLoading(false)
    }
  }

  const handleTimelapseAction = async (action: "start" | "stop") => {
    if (!details) return

    setActionLoading(action)
    try {
      const response = await fetch("/api/timelapses", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          camera_id: cameraId,
          status: action === "start" ? "running" : "stopped",
        }),
      })

      if (response.ok) {
        // Refresh camera details
        await fetchCameraDetails()
      } else {
        throw new Error(`Failed to ${action} timelapse`)
      }
    } catch (err) {
      console.error(`Failed to ${action} timelapse:`, err)
    } finally {
      setActionLoading(null)
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 B"
    const k = 1024
    const sizes = ["B", "KB", "MB", "GB"]
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
  }

  const formatRelativeTime = (timestamp: string) => {
    const now = new Date()
    const past = new Date(timestamp)
    const diffMs = now.getTime() - past.getTime()
    const diffMins = Math.floor(diffMs / (1000 * 60))
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffMins < 1) return "Just now"
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    return `${diffDays}d ago`
  }

  const getHealthStatusColor = (status: string) => {
    switch (status) {
      case "online":
        return "text-green-600 bg-green-100"
      case "offline":
        return "text-red-600 bg-red-100"
      default:
        return "text-gray-600 bg-gray-100"
    }
  }

  const getHealthStatusIcon = (status: string) => {
    switch (status) {
      case "online":
        return "🟢"
      case "offline":
        return "🔴"
      default:
        return "⚪"
    }
  }

  if (loading) {
    return (
      <div className='flex items-center justify-center min-h-screen bg-gray-50'>
        <div className='text-center'>
          <div className='w-12 h-12 mx-auto border-b-2 border-blue-600 rounded-full animate-spin'></div>
          <p className='mt-4 text-gray-600'>Loading camera details...</p>
        </div>
      </div>
    )
  }

  if (error || !details) {
    return (
      <div className='flex items-center justify-center min-h-screen bg-gray-50'>
        <div className='text-center'>
          <p className='mb-4 text-lg text-red-600'>
            {error || "Camera not found"}
          </p>
          <Link href='/' className='text-blue-600 hover:text-blue-800'>
            ← Back to Dashboard
          </Link>
        </div>
      </div>
    )
  }

  const { camera, activeTimelapse, latestImage, stats, recentLogs } = details

  return (
    <div className='min-h-screen bg-gray-50'>
      {/* Header */}
      <div className='bg-white shadow-sm'>
        <div className='px-4 py-4 mx-auto max-w-7xl sm:px-6 lg:px-8'>
          <div className='flex items-center justify-between'>
            <div className='flex items-center gap-4'>
              <Link href='/' className='text-blue-600 hover:text-blue-800'>
                ← Dashboard
              </Link>
              <h1 className='text-2xl font-bold text-gray-900'>
                {camera.name}
              </h1>
              <div className='flex items-center gap-2'>
                <span className='text-lg'>
                  {getHealthStatusIcon(camera.health_status)}
                </span>
                <span
                  className={`px-2 py-1 text-xs rounded-full ${getHealthStatusColor(
                    camera.health_status
                  )}`}
                >
                  {camera.health_status}
                </span>
              </div>
            </div>
            <div className='flex items-center gap-2'>
              {activeTimelapse?.status === "running" ? (
                <button
                  onClick={() => handleTimelapseAction("stop")}
                  disabled={actionLoading === "stop"}
                  className='px-4 py-2 text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50'
                >
                  {actionLoading === "stop" ? "Stopping..." : "Stop Timelapse"}
                </button>
              ) : (
                <button
                  onClick={() => handleTimelapseAction("start")}
                  disabled={actionLoading === "start"}
                  className='px-4 py-2 text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-50'
                >
                  {actionLoading === "start"
                    ? "Starting..."
                    : "Start Timelapse"}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className='px-4 py-8 mx-auto max-w-7xl sm:px-6 lg:px-8'>
        <div className='grid grid-cols-1 gap-8 lg:grid-cols-3'>
          {/* Main Content - Latest Image */}
          <div className='lg:col-span-2'>
            <div className='overflow-hidden bg-white rounded-lg shadow-sm'>
              <div className='p-6'>
                <h2 className='mb-4 text-lg font-semibold text-gray-900'>
                  Latest Capture
                </h2>
                <div className='overflow-hidden bg-gray-100 rounded-lg aspect-video'>
                  {latestImage ? (
                    <img
                      src={`/api/cameras/${camera.id}/latest-capture`}
                      alt={`Latest capture from ${camera.name}`}
                      className='object-cover w-full h-full'
                      onError={(e) => {
                        // Hide the image element and show placeholder instead
                        e.currentTarget.style.display = "none"
                        const parent = e.currentTarget.parentElement
                        if (
                          parent &&
                          !parent.querySelector(".image-error-placeholder")
                        ) {
                          const placeholder = document.createElement("div")
                          placeholder.className =
                            "flex items-center justify-center w-full h-full text-gray-500 image-error-placeholder"
                          placeholder.innerHTML = `
                            <div class="text-center">
                              <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                              </svg>
                              <p class="mt-2">Image not available</p>
                            </div>
                          `
                          parent.appendChild(placeholder)
                        }
                      }}
                    />
                  ) : (
                    <div className='flex items-center justify-center w-full h-full text-gray-500'>
                      <div className='text-center'>
                        <svg
                          className='w-12 h-12 mx-auto text-gray-400'
                          fill='none'
                          viewBox='0 0 24 24'
                          stroke='currentColor'
                        >
                          <path
                            strokeLinecap='round'
                            strokeLinejoin='round'
                            strokeWidth={2}
                            d='M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z'
                          />
                          <path
                            strokeLinecap='round'
                            strokeLinejoin='round'
                            strokeWidth={2}
                            d='M15 13a3 3 0 11-6 0 3 3 0 016 0z'
                          />
                        </svg>
                        <p className='mt-2'>No images captured yet</p>
                      </div>
                    </div>
                  )}
                </div>
                {latestImage && (
                  <div className='grid grid-cols-2 gap-4 mt-4 text-sm text-gray-600'>
                    <div>
                      <span className='font-medium'>Captured:</span>{" "}
                      {formatRelativeTime(latestImage.captured_at)}
                    </div>
                    <div>
                      <span className='font-medium'>Day:</span>{" "}
                      {latestImage.day_number}
                    </div>
                    <div>
                      <span className='font-medium'>File Size:</span>{" "}
                      {formatFileSize(latestImage.file_size)}
                    </div>
                    <div>
                      <span className='font-medium'>Timelapse:</span>{" "}
                      {activeTimelapse ? `#${activeTimelapse.id}` : "None"}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Recent Activity */}
            <div className='mt-8 bg-white rounded-lg shadow-sm'>
              <div className='p-6'>
                <h3 className='mb-4 text-lg font-semibold text-gray-900'>
                  Recent Activity
                </h3>
                <div className='space-y-3'>
                  {recentLogs.length > 0 ? (
                    recentLogs.map((log) => (
                      <div
                        key={log.id}
                        className='flex items-start gap-3 p-3 rounded-lg bg-gray-50'
                      >
                        <div
                          className={`px-2 py-1 text-xs rounded ${
                            log.level === "error"
                              ? "bg-red-100 text-red-600"
                              : log.level === "warning"
                              ? "bg-yellow-100 text-yellow-600"
                              : "bg-blue-100 text-blue-600"
                          }`}
                        >
                          {log.level.toUpperCase()}
                        </div>
                        <div className='flex-1'>
                          <p className='text-sm text-gray-900'>{log.message}</p>
                          <p className='mt-1 text-xs text-gray-500'>
                            {formatRelativeTime(log.timestamp)}
                          </p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className='py-4 text-center text-gray-500'>
                      No recent activity
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Sidebar - Stats and Controls */}
          <div className='space-y-6'>
            {/* Stats */}
            <div className='p-6 bg-white rounded-lg shadow-sm'>
              <h3 className='mb-4 text-lg font-semibold text-gray-900'>
                Statistics
              </h3>
              <div className='space-y-4'>
                <div className='flex justify-between'>
                  <span className='text-gray-600'>Current Timelapse</span>
                  <span className='font-semibold'>
                    {stats.currentTimelapseImages} images
                  </span>
                </div>
                <div className='flex justify-between'>
                  <span className='text-gray-600'>Total Images</span>
                  <span className='font-semibold'>{stats.totalImages}</span>
                </div>
                <div className='flex justify-between'>
                  <span className='text-gray-600'>Videos Generated</span>
                  <span className='font-semibold'>{stats.videoCount}</span>
                </div>
                <div className='flex justify-between'>
                  <span className='text-gray-600'>Days Active</span>
                  <span className='font-semibold'>
                    {stats.daysSinceFirstCapture}
                  </span>
                </div>
              </div>
            </div>

            {/* Timelapse Status */}
            <div className='p-6 bg-white rounded-lg shadow-sm'>
              <h3 className='mb-4 text-lg font-semibold text-gray-900'>
                Timelapse Status
              </h3>
              {activeTimelapse ? (
                <div className='space-y-3'>
                  <div className='flex justify-between'>
                    <span className='text-gray-600'>Status</span>
                    <span
                      className={`px-2 py-1 text-xs rounded-full ${
                        activeTimelapse.status === "running"
                          ? "bg-green-100 text-green-600"
                          : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {activeTimelapse.status}
                    </span>
                  </div>
                  <div className='flex justify-between'>
                    <span className='text-gray-600'>Started</span>
                    <span className='text-sm'>
                      {new Date(
                        activeTimelapse.start_date
                      ).toLocaleDateString()}
                    </span>
                  </div>
                  <div className='flex justify-between'>
                    <span className='text-gray-600'>Images</span>
                    <span className='text-sm'>
                      {activeTimelapse.image_count}
                    </span>
                  </div>
                  {activeTimelapse.last_capture_at && (
                    <div className='flex justify-between'>
                      <span className='text-gray-600'>Last Capture</span>
                      <span className='text-sm'>
                        {formatRelativeTime(activeTimelapse.last_capture_at)}
                      </span>
                    </div>
                  )}
                </div>
              ) : (
                <p className='py-4 text-center text-gray-500'>
                  No active timelapse
                </p>
              )}
            </div>

            {/* Camera Settings */}
            <div className='p-6 bg-white rounded-lg shadow-sm'>
              <h3 className='mb-4 text-lg font-semibold text-gray-900'>
                Camera Settings
              </h3>
              <div className='space-y-3'>
                <div className='flex justify-between'>
                  <span className='text-gray-600'>Status</span>
                  <span
                    className={`px-2 py-1 text-xs rounded-full ${
                      camera.status === "active"
                        ? "bg-green-100 text-green-600"
                        : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {camera.status}
                  </span>
                </div>
                <div className='flex justify-between'>
                  <span className='text-gray-600'>Time Window</span>
                  <span className='text-sm'>
                    {camera.use_time_window
                      ? `${camera.time_window_start} - ${camera.time_window_end}`
                      : "Disabled"}
                  </span>
                </div>
                <div className='flex justify-between'>
                  <span className='text-gray-600'>Failures</span>
                  <span className='text-sm'>{camera.consecutive_failures}</span>
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className='p-6 bg-white rounded-lg shadow-sm'>
              <h3 className='mb-4 text-lg font-semibold text-gray-900'>
                Quick Actions
              </h3>
              <div className='space-y-3'>
                <Link
                  href={`/logs?camera_id=${camera.id}`}
                  className='block w-full px-4 py-2 text-center text-blue-600 rounded-lg bg-blue-50 hover:bg-blue-100'
                >
                  View Logs
                </Link>
                <Link
                  href={`/videos?camera_id=${camera.id}`}
                  className='block w-full px-4 py-2 text-center text-green-600 rounded-lg bg-green-50 hover:bg-green-100'
                >
                  View Videos
                </Link>
                <button className='w-full px-4 py-2 text-gray-600 rounded-lg bg-gray-50 hover:bg-gray-100'>
                  Test Connection
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
