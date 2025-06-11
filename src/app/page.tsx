'use client'

import { useState, useEffect } from 'react'
import { Camera, Timelapse } from '@/lib/db'

interface Video {
  id: number
  camera_id: number
  name: string
  status: 'generating' | 'completed' | 'failed'
  file_size: number
  duration_seconds: number
  created_at: string
  camera_name?: string
}

export default function Dashboard() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [timelapses, setTimelapses] = useState<Timelapse[]>([])
  const [videos, setVideos] = useState<Video[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddCamera, setShowAddCamera] = useState(false)
  const [generatingVideo, setGeneratingVideo] = useState<number | null>(null)

  // Form state for adding cameras
  const [newCamera, setNewCamera] = useState({
    name: '',
    rtsp_url: '',
    use_time_window: false,
    time_window_start: '06:00',
    time_window_end: '18:00'
  })

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const [camerasRes, timelapsesRes, videosRes] = await Promise.all([
        fetch('/api/cameras'),
        fetch('/api/timelapses'),
        fetch('/api/videos')
      ])
      
      const camerasData = await camerasRes.json()
      const timelapsesData = await timelapsesRes.json()
      const videosData = await videosRes.json()
      
      setCameras(Array.isArray(camerasData) ? camerasData : [])
      setTimelapses(Array.isArray(timelapsesData) ? timelapsesData : [])
      setVideos(Array.isArray(videosData) ? videosData : [])
    } catch (error) {
      console.error('Failed to fetch data:', error)
      setCameras([])
      setTimelapses([])
      setVideos([])
    } finally {
      setLoading(false)
    }
  }

  const addCamera = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const response = await fetch('/api/cameras', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCamera)
      })
      
      if (response.ok) {
        setNewCamera({ 
          name: '', 
          rtsp_url: '',
          use_time_window: false,
          time_window_start: '06:00',
          time_window_end: '18:00'
        })
        setShowAddCamera(false)
        fetchData()
      }
    } catch (error) {
      console.error('Failed to add camera:', error)
    }
  }

  const removeCamera = async (cameraId: number) => {
    try {
      const response = await fetch(`/api/cameras/${cameraId}`, {
        method: 'DELETE'
      })
      
      if (response.ok) {
        fetchData()
      }
    } catch (error) {
      console.error('Failed to remove camera:', error)
    }
  }

  const toggleTimelapse = async (cameraId: number, currentStatus: string) => {
    const newStatus = currentStatus === 'running' ? 'stopped' : 'running'
    
    try {
      const response = await fetch('/api/timelapses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ camera_id: cameraId, status: newStatus })
      })
      
      const result = await response.json()
      
      if (response.ok && result.success) {
        // Success - refresh data and show success message
        fetchData()
        if (newStatus === 'running') {
          // Show success message for started timelapse
          alert('✅ Timelapse started successfully!')
        }
      } else {
        // Handle validation errors
        const errorMessage = result.details || result.error || 'Unknown error'
        alert(`❌ Cannot start timelapse:\n\n${errorMessage}`)
        
        // If it's a connectivity issue, offer to refresh camera status
        if (result.error?.includes('offline') || result.error?.includes('connection')) {
          if (confirm('\nWould you like to refresh camera status and try again?')) {
            // Refresh data to update camera health status
            await fetchData()
          }
        }
      }
    } catch (error) {
      console.error('Failed to toggle timelapse:', error)
      alert('❌ Failed to update timelapse. Please check your connection and try again.')
    }
  }

  const getTimelapseStatus = (cameraId: number) => {
    const timelapse = timelapses.find(t => t.camera_id === cameraId)
    return timelapse?.status || 'stopped'
  }

  const getCameraVideos = (cameraId: number) => {
    return videos.filter(v => v.camera_id === cameraId)
  }

  const formatLastCapture = (lastCaptureAt: string | null) => {
    if (!lastCaptureAt) return 'Never'
    
    const lastCapture = new Date(lastCaptureAt)
    const now = new Date()
    const diffMs = now.getTime() - lastCapture.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    
    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`
    return `${Math.floor(diffMins / 1440)}d ago`
  }

  const getCameraReadiness = (camera: Camera) => {
    // Check if camera is ready for timelapse
    const isEnabled = camera.status === 'active'
    const isOnline = camera.health_status === 'online'
    const hasRecentCapture = camera.last_capture_at && 
      (new Date().getTime() - new Date(camera.last_capture_at).getTime()) < 600000 // 10 minutes
    
    if (isEnabled && isOnline && hasRecentCapture) {
      return { status: 'ready', message: 'Ready for timelapse', color: 'text-green-600', bgColor: 'bg-green-50' }
    } else if (!isEnabled) {
      return { status: 'disabled', message: 'Camera disabled', color: 'text-gray-600', bgColor: 'bg-gray-50' }
    } else if (!isOnline) {
      return { status: 'offline', message: 'Camera offline - check connection', color: 'text-red-600', bgColor: 'bg-red-50' }
    } else {
      return { status: 'unknown', message: 'Camera status unknown - test connection', color: 'text-yellow-600', bgColor: 'bg-yellow-50' }
    }
  }

  const generateVideo = async (cameraId: number) => {
    setGeneratingVideo(cameraId)
    try {
      const response = await fetch('/api/videos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          camera_id: cameraId,
          framerate: 30,
          quality: 'medium'
        })
      })
      
      const result = await response.json()
      
      if (result.success) {
        console.log('Video generation started:', result)
        // Refresh data to show new video
        fetchData()
      } else {
        console.error('Video generation failed:', result.error)
        alert('Video generation failed: ' + result.error)
      }
    } catch (error) {
      console.error('Failed to generate video:', error)
      alert('Failed to generate video')
    } finally {
      setGeneratingVideo(null)
    }
  }

  const downloadVideo = (videoId: number, videoName: string) => {
    const downloadUrl = `/api/videos/${videoId}/download`
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = `${videoName}.mp4`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const deleteVideo = async (videoId: number) => {
    if (!confirm('Are you sure you want to delete this video?')) return
    
    try {
      const response = await fetch(`/api/videos/${videoId}`, {
        method: 'DELETE'
      })
      
      if (response.ok) {
        fetchData() // Refresh to remove deleted video
      } else {
        alert('Failed to delete video')
      }
    } catch (error) {
      console.error('Failed to delete video:', error)
      alert('Failed to delete video')
    }
  }

  if (loading) {
    return <div className="text-center py-8">Loading...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">Camera Dashboard</h1>
        <button
          onClick={() => setShowAddCamera(true)}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
        >
          Add Camera
        </button>
      </div>

      {/* System Status Summary */}
      {cameras.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-gray-50 rounded-lg">
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">{cameras.length}</div>
            <div className="text-sm text-gray-600">Total Cameras</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">
              {cameras.filter(c => getTimelapseStatus(c.id) === 'running').length}
            </div>
            <div className="text-sm text-gray-600">Active Timelapses</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">
              {cameras.filter(c => getCameraReadiness(c).status === 'ready').length}
            </div>
            <div className="text-sm text-gray-600">Ready Cameras</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-purple-600">{videos.length}</div>
            <div className="text-sm text-gray-600">Total Videos</div>
          </div>
        </div>
      )}

      {/* Add Camera Modal */}
      {showAddCamera && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white p-6 rounded-lg w-96">
            <h2 className="text-xl font-bold mb-4">Add New Camera</h2>
            <form onSubmit={addCamera} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Camera Name</label>
                <input
                  type="text"
                  value={newCamera.name}
                  onChange={(e) => setNewCamera({...newCamera, name: e.target.value})}
                  className="w-full p-2 border border-gray-300 rounded"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">RTSP URL</label>
                <input
                  type="url"
                  value={newCamera.rtsp_url}
                  onChange={(e) => setNewCamera({...newCamera, rtsp_url: e.target.value})}
                  className="w-full p-2 border border-gray-300 rounded"
                  placeholder="rtsp://..."
                  required
                />
              </div>
              
              {/* Time Window Settings */}
              <div className="border-t pt-4">
                <div className="flex items-center mb-3">
                  <input
                    type="checkbox"
                    id="use_time_window"
                    checked={newCamera.use_time_window}
                    onChange={(e) => setNewCamera({...newCamera, use_time_window: e.target.checked})}
                    className="mr-2"
                  />
                  <label htmlFor="use_time_window" className="text-sm font-medium">
                    Enable time window (daylight hours only)
                  </label>
                </div>
                
                {newCamera.use_time_window && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-gray-600 mb-1">Start Time</label>
                      <input
                        type="time"
                        value={newCamera.time_window_start}
                        onChange={(e) => setNewCamera({...newCamera, time_window_start: e.target.value})}
                        className="w-full p-2 border border-gray-300 rounded text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-600 mb-1">End Time</label>
                      <input
                        type="time"
                        value={newCamera.time_window_end}
                        onChange={(e) => setNewCamera({...newCamera, time_window_end: e.target.value})}
                        className="w-full p-2 border border-gray-300 rounded text-sm"
                      />
                    </div>
                  </div>
                )}
                
                {newCamera.use_time_window && (
                  <p className="text-xs text-gray-500 mt-2">
                    Camera will only capture images between {newCamera.time_window_start} and {newCamera.time_window_end}
                  </p>
                )}
              </div>
              <div className="flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setShowAddCamera(false)}
                  className="px-4 py-2 text-gray-600 border border-gray-300 rounded hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  Add Camera
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Cameras Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {cameras.map((camera) => {
          const timelapseStatus = getTimelapseStatus(camera.id)
          const cameraVideos = getCameraVideos(camera.id)
          const isGenerating = generatingVideo === camera.id
          const readiness = getCameraReadiness(camera)
          
          return (
            <div key={camera.id} className="border border-gray-300 rounded-lg p-4">
              <div className="flex justify-between items-start mb-3">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold">{camera.name}</h3>
                  {/* Camera Readiness Status */}
                  <div className={`text-sm mt-1 p-2 rounded-md ${readiness.bgColor}`}>
                    <div className={`font-medium ${readiness.color}`}>
                      {readiness.status === 'ready' && '✅ '}
                      {readiness.status === 'offline' && '🔴 '}
                      {readiness.status === 'disabled' && '⚪ '}
                      {readiness.status === 'unknown' && '⚠️ '}
                      {readiness.message}
                    </div>
                    {camera.consecutive_failures > 0 && (
                      <div className="text-red-500 text-xs mt-1">
                        {camera.consecutive_failures} consecutive failures
                      </div>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => removeCamera(camera.id)}
                  className="text-red-600 hover:text-red-800 text-sm"
                >
                  Remove
                </button>
              </div>
              
              <p className="text-sm text-gray-600 mb-3 truncate">{camera.rtsp_url}</p>
              
              {/* Time Window Display */}
              {camera.use_time_window && (
                <div className="text-xs text-blue-600 mb-3 bg-blue-50 p-2 rounded">
                  🕐 Active: {camera.time_window_start?.slice(0,5)} - {camera.time_window_end?.slice(0,5)}
                </div>
              )}

              {/* Last Capture Info */}
              <div className="text-xs text-gray-500 mb-3 bg-gray-50 p-2 rounded">
                <div className="flex justify-between">
                  <span>Last capture:</span>
                  <span className={camera.last_capture_success === false ? 'text-red-500' : ''}>
                    {formatLastCapture(camera.last_capture_at)}
                    {camera.last_capture_success === false && ' ❌'}
                    {camera.last_capture_success === true && ' ✅'}
                  </span>
                </div>
              </div>
              
              {/* Timelapse Controls */}
              <div className="flex justify-between items-center mb-4">
                <span className={`px-2 py-1 rounded text-xs ${
                  timelapseStatus === 'running' 
                    ? 'bg-green-100 text-green-800' 
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  Timelapse: {timelapseStatus}
                </span>
                
                <button
                  onClick={() => toggleTimelapse(camera.id, timelapseStatus)}
                  disabled={timelapseStatus !== 'running' && readiness.status !== 'ready'}
                  className={`px-3 py-1 rounded text-sm ${
                    timelapseStatus === 'running'
                      ? 'bg-red-600 text-white hover:bg-red-700'
                      : readiness.status === 'ready'
                      ? 'bg-green-600 text-white hover:bg-green-700'
                      : 'bg-gray-400 text-gray-200 cursor-not-allowed'
                  }`}
                  title={
                    timelapseStatus === 'running' 
                      ? 'Stop timelapse'
                      : readiness.status === 'ready'
                      ? 'Start timelapse'
                      : `Cannot start: ${readiness.message}`
                  }
                >
                  {timelapseStatus === 'running' ? 'Stop' : 'Start'}
                </button>
              </div>

              {/* Video Section */}
              <div className="border-t pt-3">
                <div className="flex justify-between items-center mb-2">
                  <h4 className="text-sm font-medium">Videos ({cameraVideos.length})</h4>
                  <button
                    onClick={() => generateVideo(camera.id)}
                    disabled={isGenerating}
                    className={`px-2 py-1 rounded text-xs ${
                      isGenerating
                        ? 'bg-gray-400 text-white cursor-not-allowed'
                        : 'bg-blue-600 text-white hover:bg-blue-700'
                    }`}
                  >
                    {isGenerating ? 'Generating...' : 'Generate Video'}
                  </button>
                </div>

                {/* Video List */}
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {cameraVideos.length === 0 ? (
                    <p className="text-xs text-gray-500 italic">No videos yet</p>
                  ) : (
                    cameraVideos.map((video) => (
                      <div key={video.id} className="flex justify-between items-center text-xs bg-gray-50 p-2 rounded">
                        <div className="flex-1 min-w-0">
                          <p className="truncate font-medium">{video.name}</p>
                          <p className="text-gray-500">
                            {video.status === 'completed' && (
                              <>
                                {video.file_size ? (video.file_size / 1024 / 1024).toFixed(1) : '0'}MB • {video.duration_seconds ? Number(video.duration_seconds).toFixed(1) : '0'}s
                              </>
                            )}
                            {video.status === 'generating' && 'Generating...'}
                            {video.status === 'failed' && 'Failed'}
                          </p>
                        </div>
                        <div className="flex gap-1 ml-2">
                          {video.status === 'completed' && (
                            <button
                              onClick={() => downloadVideo(video.id, video.name)}
                              className="text-blue-600 hover:text-blue-800"
                              title="Download"
                            >
                              ↓
                            </button>
                          )}
                          <button
                            onClick={() => deleteVideo(video.id)}
                            className="text-red-600 hover:text-red-800"
                            title="Delete"
                          >
                            ×
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {cameras.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          <p>No cameras configured yet.</p>
          <p>Click "Add Camera" to get started.</p>
        </div>
      )}
    </div>
  )
}
