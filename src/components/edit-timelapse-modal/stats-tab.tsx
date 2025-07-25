// src/components/edit-timelapse-modal/stats-tab.tsx
"use client"

import { 
  BarChart3, 
  Calendar, 
  Camera, 
  Clock, 
  HardDrive, 
  Video,
  Play,
  Timer
} from "lucide-react"
import { formatRelativeTime, formatAbsoluteTime } from "@/lib/time-utils"
import { useTimezoneSettings } from "@/contexts/settings-context"

interface StatsTabProps {
  timelapse: {
    id: number
    name: string
    status: string
    image_count: number
    start_date: string
    last_capture_at?: string
  }
  cameraId: number
  cameraName: string
  onDataChange?: () => void
}

export function StatsTab({
  timelapse,
  cameraId,
  cameraName,
  onDataChange,
}: StatsTabProps) {
  const { timezone } = useTimezoneSettings()
  
  // Calculate estimated file sizes and durations
  const estimatedFileSize = timelapse.image_count * 0.5 // Rough estimate: 0.5MB per image
  const formatFileSize = (mb: number) => {
    if (mb < 1024) return `${mb.toFixed(1)} MB`
    return `${(mb / 1024).toFixed(2)} GB`
  }
  
  const estimatedVideoDuration = Math.round(timelapse.image_count / 30) // Assuming 30 FPS
  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
  }
  
  const daysSinceStart = Math.floor(
    (Date.now() - new Date(timelapse.start_date).getTime()) / (1000 * 60 * 60 * 24)
  )

  const stats = [
    {
      icon: Calendar,
      label: "Started",
      value: formatRelativeTime(timelapse.start_date, { timezone }),
      subtitle: formatAbsoluteTime(timelapse.start_date, timezone),
      color: "text-cyan"
    },
    {
      icon: Camera,
      label: "Images Captured",
      value: timelapse.image_count.toLocaleString(),
      subtitle: `${Math.round(timelapse.image_count / Math.max(1, daysSinceStart))} per day avg`,
      color: "text-green-400"
    },
    {
      icon: Clock,
      label: "Last Capture",
      value: timelapse.last_capture_at 
        ? formatRelativeTime(timelapse.last_capture_at, { timezone })
        : "Never",
      subtitle: timelapse.last_capture_at 
        ? formatAbsoluteTime(timelapse.last_capture_at, timezone)
        : "No captures yet",
      color: "text-purple"
    },
    {
      icon: Timer,
      label: "Duration",
      value: `${daysSinceStart} days`,
      subtitle: timelapse.status === "running" ? "Active recording" : "Completed",
      color: "text-yellow-400"
    },
    {
      icon: HardDrive,
      label: "Estimated Size",
      value: formatFileSize(estimatedFileSize),
      subtitle: "Images + thumbnails",
      color: "text-pink"
    },
    {
      icon: Video,
      label: "Est. Video Length",
      value: formatDuration(estimatedVideoDuration),
      subtitle: "At 30 FPS",
      color: "text-cyan"
    }
  ]

  return (
    <div className="space-y-6">
      <div className="text-center">
        <div className="flex items-center justify-center gap-2 mb-2">
          <BarChart3 className="w-5 h-5 text-cyan" />
          <h3 className="text-xl font-semibold text-white">Timelapse Statistics</h3>
        </div>
        <p className="text-grey-light/70">
          Overview of your timelapse recording progress and metrics
        </p>
      </div>

      {/* Status Badge */}
      <div className="flex justify-center">
        <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium ${
          timelapse.status === "running" 
            ? "bg-green-500/20 text-green-400 border border-green-500/30"
            : timelapse.status === "paused"
            ? "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30"
            : "bg-blue-500/20 text-blue-400 border border-blue-500/30"
        }`}>
          {timelapse.status === "running" && <Play className="w-4 h-4" />}
          {timelapse.status === "paused" && <Timer className="w-4 h-4" />}
          {timelapse.status === "completed" && <Video className="w-4 h-4" />}
          {timelapse.status.charAt(0).toUpperCase() + timelapse.status.slice(1)}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {stats.map((stat, index) => {
          const Icon = stat.icon
          return (
            <div
              key={index}
              className="glass-strong rounded-xl p-4 hover:bg-gray-800/50 transition-all duration-300"
            >
              <div className="flex items-start gap-3">
                <div className={`p-2 rounded-lg bg-black/20 ${stat.color.replace('text-', 'bg-')}/20`}>
                  <Icon className={`w-5 h-5 ${stat.color}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-grey-light font-medium mb-1">
                    {stat.label}
                  </div>
                  <div className="text-lg font-bold text-white mb-1">
                    {stat.value}
                  </div>
                  <div className="text-xs text-grey-light/60">
                    {stat.subtitle}
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Additional Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="glass-strong rounded-xl p-4">
          <h4 className="text-white font-medium mb-3 flex items-center gap-2">
            <Camera className="w-4 h-4 text-cyan" />
            Capture Details
          </h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-grey-light">Camera:</span>
              <span className="text-white font-medium">{cameraName}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-grey-light">Timelapse ID:</span>
              <span className="text-white font-mono">#{timelapse.id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-grey-light">Status:</span>
              <span className={`font-medium ${
                timelapse.status === "running" ? "text-green-400" :
                timelapse.status === "paused" ? "text-yellow-400" : "text-blue-400"
              }`}>
                {timelapse.status}
              </span>
            </div>
          </div>
        </div>

        <div className="glass-strong rounded-xl p-4">
          <h4 className="text-white font-medium mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-purple" />
            Performance
          </h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-grey-light">Avg per day:</span>
              <span className="text-white font-medium">
                {Math.round(timelapse.image_count / Math.max(1, daysSinceStart))} images
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-grey-light">Est. video size:</span>
              <span className="text-white font-medium">
                {formatFileSize(estimatedVideoDuration * 0.1)} {/* Rough video size estimate */}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-grey-light">Compression ratio:</span>
              <span className="text-white font-medium">
                {Math.round((estimatedVideoDuration * 0.1) / estimatedFileSize * 100)}%
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}