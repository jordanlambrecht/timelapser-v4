import { Card, CardContent } from "@/components/ui/card"
import { Video, Star, PlayCircle, Camera, HardDrive, Calendar } from "lucide-react"

interface StatsDashboardProps {
  statistics?: {
    total_timelapses: number
    starred_count: number
    active_count: number
    total_images: number
    total_storage_bytes: number
    oldest_timelapse_date?: string
  }
}

export function StatsDashboard({ statistics }: StatsDashboardProps) {
  if (!statistics) {
    return (
      <div className="glass p-6 rounded-2xl">
        <div className="h-24 bg-purple/10 rounded-xl animate-pulse" />
      </div>
    )
  }

  const formatStorageSize = (bytes: number) => {
    const units = ["B", "KB", "MB", "GB", "TB"]
    let size = bytes
    let unitIndex = 0

    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024
      unitIndex++
    }

    return `${size.toFixed(size >= 100 ? 0 : 1)} ${units[unitIndex]}`
  }

  const formatDate = (dateString?: string) => {
    if (!dateString) return "Unknown"
    return new Date(dateString).toLocaleDateString("en-US", {
      month: "short",
      year: "numeric"
    })
  }

  const stats = [
    {
      icon: Video,
      label: "Total Timelapses",
      value: statistics.total_timelapses,
      color: "cyan"
    },
    {
      icon: Star,
      label: "Starred",
      value: statistics.starred_count,
      color: "yellow"
    },
    {
      icon: PlayCircle,
      label: "Active",
      value: statistics.active_count,
      color: "success"
    },
    {
      icon: Camera,
      label: "Total Images",
      value: statistics.total_images.toLocaleString(),
      color: "purple"
    },
    {
      icon: HardDrive,
      label: "Storage Used",
      value: formatStorageSize(statistics.total_storage_bytes),
      color: "pink"
    },
    {
      icon: Calendar,
      label: "Since",
      value: formatDate(statistics.oldest_timelapse_date),
      color: "grey-light"
    }
  ]

  return (
    <div className="glass p-6 rounded-2xl border border-purple-muted/30">
      <div className="flex items-center mb-6">
        <h2 className="text-lg font-semibold text-white">📊 Library Statistics</h2>
      </div>
      
      {/* Desktop Layout */}
      <div className="hidden md:grid md:grid-cols-3 lg:grid-cols-6 gap-6">
        {stats.map((stat, index) => {
          const Icon = stat.icon
          return (
            <div key={index} className="text-center space-y-3">
              <div className={`w-12 h-12 mx-auto bg-gradient-to-br from-${stat.color}/20 to-${stat.color}/30 rounded-xl flex items-center justify-center border border-${stat.color}/40`}>
                <Icon className={`w-6 h-6 text-${stat.color === 'grey-light' ? 'white' : stat.color}`} />
              </div>
              <div>
                <div className="text-2xl font-bold text-white">{stat.value}</div>
                <div className="text-sm text-grey-light/70">{stat.label}</div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Tablet Layout */}
      <div className="hidden sm:grid md:hidden grid-cols-3 gap-4">
        {stats.map((stat, index) => {
          const Icon = stat.icon
          return (
            <div key={index} className="flex items-center space-x-3 p-3 bg-black/20 rounded-xl">
              <div className={`w-10 h-10 bg-gradient-to-br from-${stat.color}/20 to-${stat.color}/30 rounded-lg flex items-center justify-center`}>
                <Icon className={`w-5 h-5 text-${stat.color === 'grey-light' ? 'white' : stat.color}`} />
              </div>
              <div>
                <div className="text-lg font-bold text-white">{stat.value}</div>
                <div className="text-xs text-grey-light/70">{stat.label}</div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Mobile Layout */}
      <div className="grid sm:hidden grid-cols-2 gap-3">
        {stats.map((stat, index) => {
          const Icon = stat.icon
          return (
            <div key={index} className="text-center space-y-2 p-3 bg-black/20 rounded-lg">
              <div className={`w-8 h-8 mx-auto bg-gradient-to-br from-${stat.color}/20 to-${stat.color}/30 rounded-lg flex items-center justify-center`}>
                <Icon className={`w-4 h-4 text-${stat.color === 'grey-light' ? 'white' : stat.color}`} />
              </div>
              <div>
                <div className="text-sm font-bold text-white">{stat.value}</div>
                <div className="text-xs text-grey-light/70">{stat.label}</div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
