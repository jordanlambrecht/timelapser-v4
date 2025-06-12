'use client'

import { useState, useEffect } from 'react'
import { Button } from "@/components/ui/button"
import { Plus, Camera, Video, Clock, Activity, Zap, Eye } from "lucide-react"
import { CameraCard } from "@/components/camera-card"
import { StatsCard } from "@/components/stats-card"
import { CameraModal } from "@/components/camera-modal"

interface Camera {
  id: number
  name: string
  rtsp_url: string
  status: string
  health_status: 'online' | 'offline' | 'unknown'
  last_capture_at?: string
  consecutive_failures: number
  time_window_start?: string
  time_window_end?: string
  use_time_window: boolean
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
      console.error('Error fetching data:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

  const handleSaveCamera = async (cameraData: any) => {
    try {
      const url = editingCamera ? `/api/cameras/${editingCamera.id}` : '/api/cameras'
      const method = editingCamera ? 'PUT' : 'POST'
      
      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cameraData)
      })

      if (response.ok) {
        fetchData()
        setEditingCamera(undefined)
      }
    } catch (error) {
      console.error('Error saving camera:', error)
    }
  }

  const handleToggleTimelapse = async (cameraId: number, currentStatus: string) => {
    try {
      const newStatus = currentStatus === 'running' ? 'stopped' : 'running'
      await fetch('/api/timelapses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ camera_id: cameraId, status: newStatus })
      })
      fetchData()
    } catch (error) {
      console.error('Error toggling timelapse:', error)
    }
  }

  const handleDeleteCamera = async (cameraId: number) => {
    if (confirm('Are you sure you want to delete this camera?')) {
      try {
        await fetch(`/api/cameras/${cameraId}`, { method: 'DELETE' })
        fetchData()
      } catch (error) {
        console.error('Error deleting camera:', error)
      }
    }
  }

  const handleGenerateVideo = async (cameraId: number) => {
    try {
      await fetch('/api/videos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ camera_id: cameraId })
      })
      fetchData()
    } catch (error) {
      console.error('Error generating video:', error)
    }
  }

  // Calculate stats
  const onlineCameras = cameras.filter(c => c.health_status === 'online').length
  const activTimelapses = timelapses.filter(t => t.status === 'running').length
  const totalVideos = videos.filter(v => v.status === 'completed').length
  const totalImages = timelapses.reduce((sum, t) => sum + (t.image_count || 0), 0)

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center space-y-6">
          <div className="relative">
            <div className="w-16 h-16 border-4 border-pink/20 border-t-pink rounded-full animate-spin mx-auto" />
            <div className="absolute inset-0 w-16 h-16 border-4 border-cyan/20 border-b-cyan rounded-full animate-spin mx-auto" style={{ animationDirection: 'reverse', animationDuration: '1.5s' }} />
          </div>
          <div>
            <p className="text-white font-medium">Loading dashboard...</p>
            <p className="text-grey-light/60 text-sm mt-1">Fetching camera data</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-12 relative">
      {/* Hero Section with Asymmetric Layout */}
      <div className="relative">
        {/* Floating accent elements */}
        <div className="absolute -top-4 right-1/4 w-2 h-2 bg-yellow/60 rounded-full floating" />
        <div className="absolute top-8 left-1/3 w-1 h-12 bg-purple/30 rounded-full floating" style={{ animationDelay: '1s' }} />
        
        <div className="grid lg:grid-cols-3 gap-8 items-end">
          <div className="lg:col-span-2 space-y-6">
            <div className="space-y-4">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 bg-gradient-to-br from-pink to-cyan rounded-xl rotate-12 floating" />
                <h1 className="text-6xl font-bold gradient-text leading-tight">
                  Control Center
                </h1>
              </div>
              <p className="text-grey-light/70 text-lg max-w-2xl">
                Monitor your RTSP cameras, manage timelapses, and create stunning videos 
                with professional-grade automation tools.
              </p>
            </div>
          </div>
          
          <div className="flex justify-end">
            <Button 
              onClick={() => setIsModalOpen(true)}
              size="lg"
              className="bg-gradient-to-r from-pink to-cyan hover:from-pink-dark hover:to-cyan text-black font-bold px-8 py-4 text-lg rounded-2xl hover:shadow-2xl hover:shadow-pink/20 transition-all duration-300 hover:scale-105"
            >
              <Plus className="w-6 h-6 mr-3" />
              Add Camera
            </Button>
          </div>
        </div>
      </div>

      {/* Stats Grid with Creative Layout */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatsCard
          title="Total Cameras"
          value={cameras.length}
          description={`${onlineCameras} online`}
          icon={Camera}
          color="cyan"
          trend={onlineCameras > 0 ? { value: Math.round((onlineCameras / cameras.length) * 100), label: "uptime" } : undefined}
        />
        <StatsCard
          title="Active Recordings"
          value={activTimelapses}
          description="Currently capturing"
          icon={Activity}
          color="success"
        />
        <StatsCard
          title="Generated Videos"
          value={totalVideos}
          description="Ready to download"
          icon={Video}
          color="purple"
        />
        <StatsCard
          title="Total Frames"
          value={totalImages.toLocaleString()}
          description="Images captured"
          icon={Zap}
          color="yellow"
        />
      </div>

      {/* Cameras Section with Dynamic Layout */}
      <div className="space-y-8">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <h2 className="text-3xl font-bold text-white">Camera Network</h2>
            <div className="flex items-center space-x-4 text-sm">
              {cameras.length > 0 && (
                <>
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-success rounded-full" />
                    <span className="text-grey-light/70">{onlineCameras} online</span>
                  </div>
                  <div className="w-1 h-4 bg-purple-muted/30 rounded-full" />
                  <div className="flex items-center space-x-2">
                    <Eye className="w-4 h-4 text-cyan/70" />
                    <span className="text-grey-light/70">{cameras.length} total</span>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {cameras.length === 0 ? (
          <div className="text-center py-16 relative">
            {/* Empty state with creative design */}
            <div className="relative max-w-md mx-auto">
              <div className="absolute -top-8 -left-8 w-4 h-4 bg-pink/40 rounded-full floating" />
              <div className="absolute -top-4 -right-6 w-2 h-2 bg-cyan/60 rounded-full floating" style={{ animationDelay: '1s' }} />
              
              <div className="glass-strong p-12 rounded-3xl border border-purple-muted/30">
                <div className="w-20 h-20 bg-gradient-to-br from-purple/20 to-cyan/20 rounded-2xl flex items-center justify-center mx-auto mb-6 rotate-12">
                  <Camera className="w-10 h-10 text-white" />
                </div>
                
                <h3 className="text-2xl font-bold text-white mb-3">No cameras yet</h3>
                <p className="text-grey-light/60 mb-8 leading-relaxed">
                  Ready to create your first timelapse? Add an RTSP camera to get started 
                  with professional automated video creation.
                </p>
                
                <Button 
                  onClick={() => setIsModalOpen(true)}
                  className="bg-gradient-to-r from-pink to-cyan hover:from-pink-dark hover:to-cyan text-black font-bold px-8 py-3 rounded-xl hover:shadow-xl transition-all duration-300"
                >
                  <Plus className="w-5 h-5 mr-2" />
                  Add Your First Camera
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8">
            {cameras.map((camera) => {
              const timelapse = timelapses.find(t => t.camera_id === camera.id)
              const cameraVideos = videos.filter(v => v.camera_id === camera.id)

              return (
                <CameraCard
                  key={camera.id}
                  camera={camera}
                  timelapse={timelapse}
                  videos={cameraVideos}
                  onToggleTimelapse={handleToggleTimelapse}
                  onEditCamera={(id) => {
                    const cam = cameras.find(c => c.id === id)
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
        title={editingCamera ? 'Edit Camera' : 'Add New Camera'}
      />
    </div>
  )
}
