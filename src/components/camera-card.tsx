import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/ui/status-badge"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { MoreVertical, Play, Square, Video, Clock, Camera, Zap } from "lucide-react"
import { cn } from "@/lib/utils"

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
  onEditCamera: (cameraId: number) => void
  onDeleteCamera: (cameraId: number) => void
  onGenerateVideo: (cameraId: number) => void
}

export function CameraCard({ 
  camera, 
  timelapse, 
  videos, 
  onToggleTimelapse, 
  onEditCamera, 
  onDeleteCamera,
  onGenerateVideo 
}: CameraCardProps) {
  const formatTimeAgo = (timestamp?: string) => {
    if (!timestamp) return "Never"
    const now = new Date()
    const time = new Date(timestamp)
    const diffInMinutes = Math.floor((now.getTime() - time.getTime()) / 60000)
    
    if (diffInMinutes < 1) return "Just now"
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)}h ago`
    return `${Math.floor(diffInMinutes / 1440)}d ago`
  }

  const completedVideos = videos.filter(v => v.status === 'completed')
  const isTimelapseRunning = timelapse?.status === 'running'

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
              <DropdownMenuItem onClick={() => onEditCamera(camera.id)} className="text-white hover:bg-cyan/20">
                Edit Camera
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onGenerateVideo(camera.id)} className="text-white hover:bg-purple/20">
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
              <Zap className="w-4 h-4 text-yellow/70" />
              <p className="text-xs text-grey-light/60 font-medium">Images</p>
            </div>
            <p className="font-bold text-white">{timelapse?.image_count || 0}</p>
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

        {/* Videos section with counter */}
        {completedVideos.length > 0 && (
          <div className="flex items-center space-x-3 p-3 rounded-xl bg-purple/10 border border-purple/20">
            <Video className="h-4 w-4 text-purple-light flex-shrink-0" />
            <div>
              <p className="text-xs text-purple-light/80 font-medium">Videos</p>
              <p className="text-sm text-white">{completedVideos.length} completed</p>
            </div>
          </div>
        )}

        {/* Enhanced Controls */}
        <div className="flex items-center justify-between pt-2">
          <div className={cn(
            "flex items-center space-x-2 px-3 py-2 rounded-full text-sm font-medium border",
            isTimelapseRunning 
              ? "bg-success/20 text-success border-success/30" 
              : "bg-grey-light/10 text-grey-light border-grey-light/20"
          )}>
            {isTimelapseRunning ? (
              <>
                <div className="w-2 h-2 bg-success rounded-full animate-pulse" />
                <span>Recording</span>
              </>
            ) : (
              <>
                <Square className="w-3 h-3" />
                <span>Stopped</span>
              </>
            )}
          </div>

          <Button
            onClick={() => onToggleTimelapse(camera.id, timelapse?.status || 'stopped')}
            size="sm"
            className={cn(
              "font-medium transition-all duration-300 min-w-[80px]",
              isTimelapseRunning 
                ? "bg-failure/80 hover:bg-failure text-white hover:shadow-lg hover:shadow-failure/20" 
                : "bg-gradient-to-r from-pink to-cyan hover:from-pink-dark hover:to-cyan text-black hover:shadow-lg"
            )}
          >
            {isTimelapseRunning ? (
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
      </CardContent>
    </Card>
  )
}
