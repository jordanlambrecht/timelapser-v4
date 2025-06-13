import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/ui/status-badge"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { TimelapseModal } from "@/components/timelapse-modal"
import { VideoNameModal } from "@/components/video-name-modal"
import { VideoProgressModal } from "@/components/video-progress-modal"
import { MoreVertical, Play, Square, Video, Clock, Camera, Zap, Eye, Image as ImageIcon, Pause, Timer } from "lucide-react"
import { cn } from "@/lib/utils"
import Link from "next/link"
import Image from "next/image"
import { useState, useEffect } from "react"
import { toast } from "sonner"

interface CameraCardProps {
  camera: {
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
  }
  timelapse?: {
    id: number
    status: string
    image_count: number
    last_capture_at?: string
  }
  videos: Array<{
    id: number
    status: string
    file_size?: number
    duration?: number
    created_at: string
  }>
  onToggleTimelapse: (cameraId: number, currentStatus: string) => void
  onPauseTimelapse?: (cameraId: number) => void
  onResumeTimelapse?: (cameraId: number) => void
  onEditCamera: (cameraId: number) => void
  onDeleteCamera: (cameraId: number) => void
  onGenerateVideo: (cameraId: number) => void
}

export function CameraCard({ 
  camera, 
  timelapse, 
  videos, 
  onToggleTimelapse, 
  onPauseTimelapse,
  onResumeTimelapse,
  onEditCamera, 
  onDeleteCamera,
  onGenerateVideo 
}: CameraCardProps) {
  const [imageError, setImageError] = useState(false);
  const [imageLoading, setImageLoading] = useState(true);
  const [imageKey, setImageKey] = useState(Date.now()); // Force image reload
  const [nextCaptureCountdown, setNextCaptureCountdown] = useState<string>("");
  const [captureInterval, setCaptureInterval] = useState(300); // Default fallback
  const [actualImageCount, setActualImageCount] = useState<number | null>(null);
  const [timelapseModalOpen, setTimelapseModalOpen] = useState(false);
  const [videoNameModalOpen, setVideoNameModalOpen] = useState(false);
  const [videoProgressModalOpen, setVideoProgressModalOpen] = useState(false);
  const [currentVideoName, setCurrentVideoName] = useState('');

  // Server-Sent Events for real-time updates
  useEffect(() => {
    const eventSource = new EventSource('/api/events')
    
    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        
        // Handle different event types
        switch (data.type) {
          case 'image_captured':
            if (data.camera_id === camera.id) {
              console.log(`New image captured for camera ${camera.id}`)
              setImageKey(Date.now()) // Force image reload
              setImageError(false) // Reset error state
              setImageLoading(true) // Show loading state
              
              // Update image count if provided
              if (data.image_count !== undefined) {
                setActualImageCount(data.image_count)
              }
            }
            break
          case 'camera_status_changed':
            if (data.camera_id === camera.id) {
              console.log(`Camera ${camera.id} status changed to ${data.status}`)
              // Let the parent component handle status updates via normal refresh
            }
            break
          case 'connected':
            console.log('SSE connected to camera events')
            break
          case 'heartbeat':
            // Keep connection alive
            break
          default:
            console.log('Unknown SSE event:', data.type)
        }
      } catch (error) {
        console.error('Error parsing SSE event:', error)
      }
    }

    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error)
    }

    // Cleanup on unmount
    return () => {
      eventSource.close()
    }
  }, [camera.id])

  // Fetch accurate image count from images table (reduced frequency)
  useEffect(() => {
    const fetchImageCount = async () => {
      if (!timelapse?.id) return;
      
      try {
        const response = await fetch(`/api/images/count?timelapse_id=${timelapse.id}`);
        if (response.ok) {
          const data = await response.json();
          setActualImageCount(data.count);
        }
      } catch (error) {
        console.error('Failed to fetch image count:', error);
      }
    };

    fetchImageCount();
    // Only check occasionally as backup - SSE handles real-time updates
    const interval = setInterval(fetchImageCount, 60000); // Every minute as backup
    return () => clearInterval(interval);
  }, [timelapse?.id]);

  // Fetch settings on component mount
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await fetch('/api/settings');
        if (response.ok) {
          const settings = await response.json();
          const interval = parseInt(settings.capture_interval || '300');
          setCaptureInterval(interval);
        }
      } catch (error) {
        console.error('Failed to fetch settings:', error);
      }
    };

    fetchSettings();
  }, []);

  const isWithinTimeWindow = (camera: any): boolean => {
    if (!camera.use_time_window || !camera.time_window_start || !camera.time_window_end) {
      return true; // No time window restrictions
    }

    const now = new Date();
    const currentTime = now.getHours() * 60 + now.getMinutes(); // Convert to minutes since midnight
    
    const [startHour, startMin] = camera.time_window_start.split(':').map(Number);
    const [endHour, endMin] = camera.time_window_end.split(':').map(Number);
    
    const startTime = startHour * 60 + startMin;
    const endTime = endHour * 60 + endMin;
    
    if (startTime <= endTime) {
      // Normal time window (e.g., 06:00 - 20:00)
      return currentTime >= startTime && currentTime <= endTime;
    } else {
      // Overnight time window (e.g., 22:00 - 06:00)
      return currentTime >= startTime || currentTime <= endTime;
    }
  };

  const formatTimeAgo = (timestamp?: string) => {
    if (!timestamp) return "Never"
    
    // Handle different timestamp formats
    const time = new Date(timestamp)
    if (isNaN(time.getTime())) return "Invalid time"
    
    const now = new Date()
    const diffInSeconds = Math.floor((now.getTime() - time.getTime()) / 1000)
    
    if (diffInSeconds < 60) return "Just now"
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`
    if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)}h ago`
    return `${Math.floor(diffInSeconds / 86400)}d ago`
  }

  const formatCountdown = (seconds: number): string => {
    if (seconds <= 0) return "Due now"
    
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    
    if (mins > 0) {
      return `${mins}m ${secs}s`
    }
    return `${secs}s`
  }

  // Define these variables before the useEffect that uses them
  const completedVideos = videos.filter(v => v.status === 'completed')
  const completedTimelapses = videos.length // Total timelapses (completed videos)
  const isTimelapseRunning = timelapse?.status === 'running'
  const isTimelapsePaused = timelapse?.status === 'paused'

  // Real-time countdown for next capture
  useEffect(() => {
    const updateCountdown = () => {
      if (!isTimelapseRunning) {
        setNextCaptureCountdown("")
        return
      }

      // Check if we're within the time window
      if (!isWithinTimeWindow(camera)) {
        const now = new Date();
        const tomorrow = new Date(now);
        tomorrow.setDate(tomorrow.getDate() + 1);
        
        // Calculate next window start time
        const [startHour, startMin] = (camera.time_window_start || '06:00:00').split(':').map(Number);
        let nextWindowStart = new Date(now);
        nextWindowStart.setHours(startHour, startMin, 0, 0);
        
        // If start time has passed today, use tomorrow
        if (nextWindowStart <= now) {
          nextWindowStart = new Date(tomorrow);
          nextWindowStart.setHours(startHour, startMin, 0, 0);
        }
        
        const timeUntilWindow = Math.floor((nextWindowStart.getTime() - now.getTime()) / 1000);
        const hours = Math.floor(timeUntilWindow / 3600);
        const mins = Math.floor((timeUntilWindow % 3600) / 60);
        
        if (hours > 0) {
          setNextCaptureCountdown(`Window opens in ${hours}h ${mins}m`);
        } else {
          setNextCaptureCountdown(`Window opens in ${mins}m`);
        }
        return
      }

      const lastCaptureTime = camera.last_capture_at || timelapse?.last_capture_at
      
      if (!lastCaptureTime) {
        setNextCaptureCountdown("First capture due")
        return
      }

      const lastCapture = new Date(lastCaptureTime)
      if (isNaN(lastCapture.getTime())) {
        setNextCaptureCountdown("Invalid timestamp")
        return
      }

      const nextCaptureTime = new Date(lastCapture.getTime() + (captureInterval * 1000))
      const now = new Date()
      const secondsUntilNext = Math.floor((nextCaptureTime.getTime() - now.getTime()) / 1000)
      
      // Debug logging (remove this later)
      if (secondsUntilNext > 3600) { // More than 1 hour seems wrong
        console.log('Countdown Debug:', {
          lastCaptureTime,
          lastCapture: lastCapture.toISOString(),
          captureInterval,
          nextCaptureTime: nextCaptureTime.toISOString(),
          now: now.toISOString(),
          secondsUntilNext,
          minutesUntilNext: Math.floor(secondsUntilNext / 60)
        })
      }
      
      if (secondsUntilNext <= 0) {
        setNextCaptureCountdown("Due now")
      } else {
        setNextCaptureCountdown(formatCountdown(secondsUntilNext))
      }
    }

    updateCountdown()
    const interval = setInterval(updateCountdown, 1000)
    
    return () => clearInterval(interval)
  }, [camera.last_capture_at, timelapse?.last_capture_at, captureInterval, isTimelapseRunning, camera.use_time_window, camera.time_window_start, camera.time_window_end])

  const handlePauseResume = () => {
    if (isTimelapsePaused && onResumeTimelapse) {
      onResumeTimelapse(camera.id)
    } else if (isTimelapseRunning && onPauseTimelapse) {
      onPauseTimelapse(camera.id)
    }
  }

  const generateDefaultVideoName = () => {
    const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-')
    return `${camera.name}_timelapse_${timestamp}`
  }

  const handleGenerateVideoClick = () => {
    const defaultName = generateDefaultVideoName()
    setCurrentVideoName(defaultName)
    setVideoNameModalOpen(true)
  }

  const handleVideoNameConfirm = async (videoName: string) => {
    setVideoNameModalOpen(false)
    setCurrentVideoName(videoName)
    setVideoProgressModalOpen(true)

    try {
      const response = await fetch('/api/videos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          camera_id: camera.id,
          video_name: videoName
        })
      })

      const result = await response.json()
      
      setVideoProgressModalOpen(false)

      if (result.success) {
        toast.success('Video generated successfully!', {
          description: `${videoName}.mp4 is ready for download`,
          duration: 5000,
        })
        
        // Refresh data to show new video
        if (onGenerateVideo) {
          onGenerateVideo(camera.id)
        }
      } else {
        toast.error('Video generation failed', {
          description: result.error || 'An unknown error occurred',
          duration: 7000,
        })
      }
    } catch (error) {
      setVideoProgressModalOpen(false)
      toast.error('Video generation failed', {
        description: 'Network error or server unavailable',
        duration: 7000,
      })
      console.error('Error generating video:', error)
    }
  }

  return (
    <Card className="glass hover-lift hover:glow relative overflow-hidden group">
      {/* Animated corner accent */}
      <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-pink/20 to-transparent rounded-bl-3xl opacity-50" />
      
      <CardHeader className="pb-4 relative">
        <div className="flex items-start justify-between">
          <div className="space-y-3 flex-1">
            <div className="flex items-center space-x-3">
              <div className={cn(
                "p-2 rounded-xl bg-gradient-to-br transition-all duration-300",
                camera.health_status === 'online' ? "from-success/20 to-cyan/20" :
                camera.health_status === 'offline' ? "from-failure/20 to-purple-dark/20" :
                "from-warn/20 to-yellow/20"
              )}>
                <Camera className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="font-bold text-lg text-white group-hover:text-pink transition-colors">
                  {camera.name}
                </h3>
                <StatusBadge status={camera.health_status} />
              </div>
            </div>
          </div>
          
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button 
                variant="ghost" 
                size="sm" 
                className="opacity-0 group-hover:opacity-100 transition-all duration-300 hover:bg-purple-muted/20 text-white"
              >
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="glass-strong border-purple-muted/30">
              <DropdownMenuItem asChild>
                <Link href={`/cameras/${camera.id}`} className="flex items-center text-white hover:bg-cyan/20 cursor-pointer">
                  <Eye className="h-4 w-4 mr-2" />
                  View Details
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEditCamera(camera.id)} className="text-white hover:bg-cyan/20">
                Edit Camera
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleGenerateVideoClick} className="text-white hover:bg-purple/20">
                Generate Video
              </DropdownMenuItem>
              <DropdownMenuItem 
                onClick={() => onDeleteCamera(camera.id)}
                className="text-failure hover:bg-failure/20"
              >
                Delete Camera
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>

      {/* Camera Image Preview */}
      <div className="px-6 pb-4">
        <div className="relative aspect-video rounded-xl overflow-hidden bg-gray-900/50 border border-gray-700/50 backdrop-blur-sm">
          {imageLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-900/70 backdrop-blur-sm">
              <div className="flex flex-col items-center space-y-3">
                <div className="w-8 h-8 border-2 border-cyan/30 border-t-cyan rounded-full animate-spin" />
                <p className="text-xs text-gray-400 font-medium">Loading preview...</p>
              </div>
            </div>
          )}
          
          {imageError ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900/70 backdrop-blur-sm">
              <div className="text-center space-y-3">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple/20 to-cyan/20 flex items-center justify-center">
                  <Camera className="w-6 h-6 text-white/70" />
                </div>
                <div>
                  <p className="text-sm text-white font-medium">No captures yet</p>
                  <p className="text-xs text-gray-400 mt-1">
                    {timelapse?.status === 'running' ? 'First image coming soon' : 'Start timelapse to capture'}
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <Image
              key={imageKey} // Force reload when imageKey changes
              src={`/api/cameras/${camera.id}/latest-capture`}
              alt={`Last capture from ${camera.name}`}
              fill
              className={cn(
                "object-cover transition-all duration-500",
                imageLoading ? "opacity-0 scale-105" : "opacity-100 scale-100"
              )}
              onLoad={() => setImageLoading(false)}
              onError={() => {
                setImageError(true);
                setImageLoading(false);
              }}
              sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
              unoptimized // Disable Next.js optimization for dynamic content
            />
          )}
          
          {/* Image overlay with info */}
          <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent p-3">
            <div className="flex items-center justify-between text-white text-xs">
              <div className="flex items-center space-x-2">
                <div className="p-1 rounded-md bg-white/10 backdrop-blur-sm">
                  <ImageIcon className="w-3 h-3" />
                </div>
                <span className="font-medium">Latest frame</span>
              </div>
              <div className={cn(
                "px-2 py-1 rounded-full text-xs font-medium backdrop-blur-sm border",
                camera.health_status === 'online' ? "bg-green-500/20 text-green-300 border-green-500/30" :
                camera.health_status === 'offline' ? "bg-red-500/20 text-red-300 border-red-500/30" :
                "bg-yellow-500/20 text-yellow-300 border-yellow-500/30"
              )}>
                {formatTimeAgo(camera.last_capture_at || timelapse?.last_capture_at)}
              </div>
            </div>
          </div>

          {/* Status indicator dot */}
          <div className="absolute top-3 right-3">
            <div className={cn(
              "w-3 h-3 rounded-full border-2 border-white/50",
              camera.health_status === 'online' ? "bg-green-500 shadow-lg shadow-green-500/50" :
              camera.health_status === 'offline' ? "bg-red-500 shadow-lg shadow-red-500/50" :
              "bg-yellow-500 shadow-lg shadow-yellow-500/50"
            )} />
          </div>
        </div>
      </div>

      <CardContent className="space-y-6">
        {/* Stats Grid with visual enhancement */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-black/20 rounded-xl p-3 border border-purple-muted/20">
            <div className="flex items-center space-x-2 mb-1">
              <Clock className="w-4 h-4 text-cyan/70" />
              <p className="text-xs text-grey-light/60 font-medium">Last Capture</p>
            </div>
            <p className="font-bold text-white">
              {formatTimeAgo(camera.last_capture_at || timelapse?.last_capture_at)}
            </p>
            {camera.consecutive_failures > 0 && (
              <p className="text-xs text-failure mt-1">
                {camera.consecutive_failures} failures
              </p>
            )}
          </div>
          
          <div className="bg-black/20 rounded-xl p-3 border border-purple-muted/20">
            <div className="flex items-center space-x-2 mb-1">
              <Timer className="w-4 h-4 text-green-400/70" />
              <p className="text-xs text-grey-light/60 font-medium">Next Capture</p>
            </div>
            <p className="font-bold text-white">
              {isTimelapseRunning ? (nextCaptureCountdown || "Calculating...") : 
               isTimelapsePaused ? "Paused" : "Stopped"}
            </p>
            {isTimelapsePaused && (
              <p className="text-xs text-yellow-400 mt-1">Paused</p>
            )}
          </div>
        </div>

        {/* Bottom Stats Grid */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-black/20 rounded-xl p-3 border border-purple-muted/20">
            <div className="flex items-center space-x-2 mb-1">
              <Zap className="w-4 h-4 text-yellow/70" />
              <p className="text-xs text-grey-light/60 font-medium">Images</p>
            </div>
            <p className="font-bold text-white">
              {actualImageCount !== null ? actualImageCount : (timelapse?.image_count || 0)}
            </p>
          </div>

          <div 
            className="bg-black/20 rounded-xl p-3 border border-purple-muted/20 cursor-pointer hover:bg-purple/10 hover:border-purple/30 transition-all duration-200"
            onClick={() => setTimelapseModalOpen(true)}
          >
            <div className="flex items-center space-x-2 mb-1">
              <Video className="w-4 h-4 text-purple-light/70" />
              <p className="text-xs text-grey-light/60 font-medium">Timelapses</p>
            </div>
            <p className="font-bold text-white">{completedTimelapses}</p>
            {completedTimelapses > 0 && (
              <p className="text-xs text-purple-light/70 mt-1">Click to view</p>
            )}
          </div>
        </div>

        {/* Time Window with enhanced styling */}
        {camera.use_time_window && camera.time_window_start && camera.time_window_end && (
          <div className="flex items-center space-x-3 p-3 rounded-xl bg-cyan/10 border border-cyan/20">
            <Clock className="h-4 w-4 text-cyan flex-shrink-0" />
            <div>
              <p className="text-xs text-cyan/80 font-medium">Active Window</p>
              <p className="text-sm text-white font-mono">
                {camera.time_window_start} - {camera.time_window_end}
              </p>
            </div>
          </div>
        )}

        {/* Enhanced Controls */}
        <div className="flex items-center justify-between pt-2">
          <div className={cn(
            "flex items-center space-x-2 px-3 py-2 rounded-full text-sm font-medium border",
            isTimelapseRunning 
              ? isWithinTimeWindow(camera)
                ? "bg-success/20 text-success border-success/30" 
                : "bg-purple/20 text-purple-light border-purple/30"
              : isTimelapsePaused
              ? "bg-yellow-500/20 text-yellow-400 border-yellow-500/30"
              : "bg-grey-light/10 text-grey-light border-grey-light/20"
          )}>
            {isTimelapseRunning ? (
              isWithinTimeWindow(camera) ? (
                <>
                  <div className="w-2 h-2 bg-success rounded-full animate-pulse" />
                  <span>Recording</span>
                </>
              ) : (
                <>
                  <div className="w-2 h-2 bg-purple-light rounded-full animate-pulse" />
                  <span>Snoozing</span>
                </>
              )
            ) : isTimelapsePaused ? (
              <>
                <Pause className="w-3 h-3" />
                <span>Paused</span>
              </>
            ) : (
              <>
                <Square className="w-3 h-3" />
                <span>Stopped</span>
              </>
            )}
          </div>

          <div className="flex items-center space-x-2">
            {/* Pause/Resume button - only show when running or paused */}
            {(isTimelapseRunning || isTimelapsePaused) && (
              <Button
                onClick={handlePauseResume}
                size="sm"
                variant="outline"
                className="border-gray-600 text-white hover:bg-gray-700 min-w-[80px]"
              >
                {isTimelapsePaused ? (
                  <>
                    <Play className="w-4 h-4 mr-1" />
                    Resume
                  </>
                ) : (
                  <>
                    <Pause className="w-4 h-4 mr-1" />
                    Pause
                  </>
                )}
              </Button>
            )}

            {/* Main Start/Stop button */}
            <Button
              onClick={() => onToggleTimelapse(camera.id, timelapse?.status || 'stopped')}
              size="sm"
              className={cn(
                "font-medium transition-all duration-300 min-w-[80px]",
                (isTimelapseRunning || isTimelapsePaused)
                  ? "bg-failure/80 hover:bg-failure text-white hover:shadow-lg hover:shadow-failure/20" 
                  : "bg-gradient-to-r from-pink to-cyan hover:from-pink-dark hover:to-cyan text-black hover:shadow-lg"
              )}
            >
              {(isTimelapseRunning || isTimelapsePaused) ? (
                <>
                  <Square className="w-4 h-4 mr-1" />
                  Stop
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-1" />
                  Start
                </>
              )}
            </Button>
          </div>
        </div>
      </CardContent>

      {/* Timelapse Modal */}
      <TimelapseModal
        isOpen={timelapseModalOpen}
        onClose={() => setTimelapseModalOpen(false)}
        cameraId={camera.id}
        cameraName={camera.name}
      />

      {/* Video Name Modal */}
      <VideoNameModal
        isOpen={videoNameModalOpen}
        onClose={() => setVideoNameModalOpen(false)}
        onConfirm={handleVideoNameConfirm}
        cameraName={camera.name}
        defaultName={currentVideoName}
      />

      {/* Video Progress Modal */}
      <VideoProgressModal
        isOpen={videoProgressModalOpen}
        cameraName={camera.name}
        videoName={currentVideoName}
        imageCount={actualImageCount || timelapse?.image_count || 0}
      />
    </Card>
  )
}
