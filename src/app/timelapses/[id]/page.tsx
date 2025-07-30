"use client"

import { useState, useEffect } from "react"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { ArrowLeft, Camera, Calendar, ImageIcon, Video, Star, Settings, Download, Trash2, Play, Clock, Layers, Info } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useTimelapseDetails } from "@/hooks/use-timelapse-details"
import { formatRelativeTime, formatAbsoluteTime } from "@/lib/time-utils"
import { toast } from "@/lib/toast"
import { TimelapseOverlaySettings } from "@/components/timelapse-overlay-settings"

export default function TimelapseDetailPage() {
  const params = useParams()
  const router = useRouter()
  const timelapseId = parseInt(params?.id as string)

  const {
    timelapse,
    camera,
    images,
    videos,
    loading,
    error,
    refetch
  } = useTimelapseDetails(timelapseId)

  const [isStarred, setIsStarred] = useState(false)
  const [activeTab, setActiveTab] = useState("overview")

  useEffect(() => {
    if (timelapse) {
      // TODO: Get starred status from API or timelapse data
      setIsStarred(false)
    }
  }, [timelapse])

  const handleStarToggle = async () => {
    try {
      // TODO: Implement star/unstar API call
      setIsStarred(!isStarred)
      toast.success(isStarred ? "Removed from starred" : "Added to starred")
    } catch (error) {
      toast.error("Failed to update starred status")
    }
  }

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to delete this timelapse? This action cannot be undone.")) {
      return
    }

    try {
      // TODO: Implement delete API call
      toast.success("Timelapse deleted successfully")
      router.push("/timelapses")
    } catch (error) {
      toast.error("Failed to delete timelapse")
    }
  }

  const handleDownloadImages = async () => {
    try {
      // TODO: Implement download images as ZIP
      toast.success("Starting download...")
    } catch (error) {
      toast.error("Failed to start download")
    }
  }

  if (loading) {
    return (
      <div className="relative space-y-8">
        {/* Header Skeleton */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="w-20 h-10 bg-purple/20 rounded-lg animate-pulse" />
            <div className="space-y-2">
              <div className="h-8 w-64 bg-purple/20 rounded animate-pulse" />
              <div className="h-4 w-32 bg-purple/10 rounded animate-pulse" />
            </div>
          </div>
          <div className="flex space-x-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="w-24 h-8 bg-purple/10 rounded animate-pulse" />
            ))}
          </div>
        </div>

        {/* Stats Grid Skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="glass p-4 rounded-xl">
              <div className="h-20 bg-purple/10 rounded animate-pulse" />
            </div>
          ))}
        </div>

        {/* Content Skeleton */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="glass p-6 rounded-xl">
            <div className="h-48 bg-purple/10 rounded animate-pulse" />
          </div>
          <div className="glass p-6 rounded-xl">
            <div className="h-48 bg-purple/10 rounded animate-pulse" />
          </div>
        </div>
      </div>
    )
  }

  if (error || !timelapse) {
    return (
      <div className="relative space-y-8">
        <div className="flex items-center justify-center min-h-[40vh]">
          <div className="glass-strong p-8 rounded-2xl text-center max-w-md">
            <div className="w-16 h-16 mx-auto mb-4 bg-failure/20 rounded-xl flex items-center justify-center">
              <Video className="w-8 h-8 text-failure" />
            </div>
            <h2 className="text-xl font-semibold text-white mb-2">
              {error || "Timelapse not found"}
            </h2>
            <div className="space-x-4 mt-6">
              <Link href="/timelapses">
                <Button 
                  variant="outline"
                  className="bg-black/30 border-purple-muted/30 text-white hover:bg-purple/20"
                >
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Back to Library
                </Button>
              </Link>
              <Button 
                onClick={refetch}
                className="bg-gradient-to-r from-pink to-cyan text-black font-medium"
              >
                Try Again
              </Button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const getStatusBadge = (status: string) => {
    const statusConfig = {
      running: { 
        color: "bg-success/20 text-success border-success/40", 
        icon: "🟢"
      },
      paused: { 
        color: "bg-warn/20 text-warn border-warn/40", 
        icon: "⏸️"
      },
      stopped: { 
        color: "bg-purple/20 text-purple-light border-purple/40", 
        icon: "⏹️"
      },
      completed: { 
        color: "bg-cyan/20 text-cyan border-cyan/40", 
        icon: "✅"
      },
      archived: { 
        color: "bg-grey-light/20 text-grey-light border-grey-light/40", 
        icon: "📦"
      }
    } as const

    const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.completed

    return (
      <Badge className={`${config.color} px-3 py-1 rounded-full border`}>
        {config.icon} {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    )
  }

  const calculateDuration = () => {
    if (!timelapse.start_date) return 0
    const start = new Date(timelapse.start_date)
    const end = timelapse.status === 'completed' && timelapse.updated_at 
      ? new Date(timelapse.updated_at) 
      : new Date()
    return Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24))
  }

  return (
    <div className="relative space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link href="/timelapses">
            <Button 
              variant="ghost" 
              size="sm"
              className="text-white hover:bg-purple/20"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Library
            </Button>
          </Link>
          <div>
            <h1 className="text-4xl font-bold gradient-text">
              {timelapse.name || `Timelapse #${timelapse.id}`}
            </h1>
            <div className="flex items-center space-x-3 mt-2">
              <div className="flex items-center space-x-2">
                <Camera className="h-4 w-4 text-cyan" />
                <span className="text-grey-light">{camera?.name || "Unknown Camera"}</span>
              </div>
              {getStatusBadge(timelapse.status)}
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleStarToggle}
            className={`${
              isStarred 
                ? "bg-yellow/20 border-yellow/40 text-yellow-400" 
                : "bg-black/30 border-purple-muted/30 text-white hover:bg-purple/20"
            }`}
          >
            <Star className={`h-4 w-4 mr-2 ${isStarred ? "fill-current" : ""}`} />
            {isStarred ? "Starred" : "Star"}
          </Button>
          <Button 
            variant="outline" 
            size="sm"
            className="bg-black/30 border-purple-muted/30 text-white hover:bg-purple/20"
          >
            <Settings className="h-4 w-4 mr-2" />
            Settings
          </Button>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={handleDownloadImages}
            className="bg-black/30 border-cyan/40 text-cyan hover:bg-cyan/10"
          >
            <Download className="h-4 w-4 mr-2" />
            Download Images
          </Button>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={handleDelete}
            className="bg-black/30 border-failure/40 text-failure hover:bg-failure/10"
          >
            <Trash2 className="h-4 w-4 mr-2" />
            Delete
          </Button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="glass p-4 rounded-xl border border-purple-muted/30">
          <div className="flex items-center space-x-3 mb-2">
            <div className="w-8 h-8 bg-gradient-to-br from-purple/30 to-cyan/30 rounded-lg flex items-center justify-center">
              <ImageIcon className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm text-grey-light/70">Images Captured</span>
          </div>
          <div className="text-2xl font-bold text-white">{timelapse.image_count.toLocaleString()}</div>
        </div>

        <div className="glass p-4 rounded-xl border border-purple-muted/30">
          <div className="flex items-center space-x-3 mb-2">
            <div className="w-8 h-8 bg-gradient-to-br from-cyan/30 to-pink/30 rounded-lg flex items-center justify-center">
              <Video className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm text-grey-light/70">Videos Generated</span>
          </div>
          <div className="text-2xl font-bold text-white">{videos?.length || 0}</div>
        </div>

        <div className="glass p-4 rounded-xl border border-purple-muted/30">
          <div className="flex items-center space-x-3 mb-2">
            <div className="w-8 h-8 bg-gradient-to-br from-yellow/30 to-purple/30 rounded-lg flex items-center justify-center">
              <Clock className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm text-grey-light/70">Duration</span>
          </div>
          <div className="text-2xl font-bold text-white">
            {calculateDuration()} days
          </div>
        </div>

        <div className="glass p-4 rounded-xl border border-purple-muted/30">
          <div className="flex items-center space-x-3 mb-2">
            <div className="w-8 h-8 bg-gradient-to-br from-pink/30 to-cyan/30 rounded-lg flex items-center justify-center">
              <Camera className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm text-grey-light/70">Last Capture</span>
          </div>
          <div className="text-sm text-white">
            {timelapse.last_capture_at ? (
              <>
                <div className="font-medium">
                  {formatRelativeTime(timelapse.last_capture_at)}
                </div>
                <div className="text-grey-light/60 text-xs">
                  {formatAbsoluteTime(timelapse.last_capture_at)}
                </div>
              </>
            ) : (
              "No captures yet"
            )}
          </div>
        </div>
      </div>

      {/* Tabbed Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="grid w-full grid-cols-3 bg-gray-900/50 border border-gray-700">
          <TabsTrigger 
            value="overview" 
            className="data-[state=active]:bg-purple/20 data-[state=active]:text-purple-light"
          >
            <Info className="w-4 h-4 mr-2" />
            Overview
          </TabsTrigger>
          <TabsTrigger 
            value="overlays"
            className="data-[state=active]:bg-purple/20 data-[state=active]:text-purple-light"
          >
            <Layers className="w-4 h-4 mr-2" />
            Overlays
          </TabsTrigger>
          <TabsTrigger 
            value="settings"
            className="data-[state=active]:bg-purple/20 data-[state=active]:text-purple-light"
          >
            <Settings className="w-4 h-4 mr-2" />
            Settings
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          {/* Content Sections */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Recent Images */}
            <div className="glass p-6 rounded-xl border border-purple-muted/30">
              <div className="flex items-center mb-4">
                <ImageIcon className="h-5 w-5 mr-2 text-cyan" />
                <h3 className="text-lg font-semibold text-white">Recent Images</h3>
              </div>
              {images && images.length > 0 ? (
                <div className="grid grid-cols-3 gap-3">
                  {images.slice(0, 6).map((image) => (
                    <div key={image.id} className="aspect-video bg-black/40 rounded-lg border border-purple-muted/20 overflow-hidden hover:border-cyan/40 transition-colors">
                      {/* TODO: Add image thumbnail component */}
                      <div className="w-full h-full flex items-center justify-center text-grey-light/40">
                        <ImageIcon className="h-8 w-8" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <ImageIcon className="h-12 w-12 mx-auto text-grey-light/40 mb-3" />
                  <p className="text-grey-light/60">No images captured yet</p>
                </div>
              )}
            </div>

            {/* Generated Videos */}
            <div className="glass p-6 rounded-xl border border-purple-muted/30">
              <div className="flex items-center mb-4">
                <Video className="h-5 w-5 mr-2 text-pink" />
                <h3 className="text-lg font-semibold text-white">Generated Videos</h3>
              </div>
              {videos && videos.length > 0 ? (
                <div className="space-y-3">
                  {videos.slice(0, 5).map((video) => (
                    <div key={video.id} className="flex items-center justify-between p-3 bg-black/30 rounded-lg border border-purple-muted/20">
                      <div>
                        <div className="font-medium text-white">{video.name}</div>
                        <div className="text-sm text-grey-light/60">
                          {video.duration_seconds ? `${Math.round(video.duration_seconds)}s` : "Unknown duration"} • 
                          {video.calculated_fps ? ` ${Math.round(video.calculated_fps)} FPS` : ""}
                        </div>
                      </div>
                      <Badge 
                        className={
                          video.status === "completed" 
                            ? "bg-success/20 text-success border-success/40" 
                            : "bg-warn/20 text-warn border-warn/40"
                        }
                      >
                        {video.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <Video className="h-12 w-12 mx-auto text-grey-light/40 mb-3" />
                  <p className="text-grey-light/60">No videos generated yet</p>
                </div>
              )}
            </div>
          </div>

          {/* Timelapse Information */}
          <div className="glass p-6 rounded-xl border border-purple-muted/30">
            <h3 className="text-lg font-semibold text-white mb-4">Timelapse Information</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="text-sm font-medium text-grey-light/70">Created</label>
                <p className="text-white mt-1">{formatAbsoluteTime(timelapse.created_at)}</p>
              </div>
              <div>
                <label className="text-sm font-medium text-grey-light/70">Status</label>
                <div className="mt-1">{getStatusBadge(timelapse.status)}</div>
              </div>
              {timelapse.start_date && (
                <div>
                  <label className="text-sm font-medium text-grey-light/70">Start Date</label>
                  <p className="text-white mt-1">{formatAbsoluteTime(timelapse.start_date)}</p>
                </div>
              )}
              {timelapse.auto_stop_at && (
                <div>
                  <label className="text-sm font-medium text-grey-light/70">Auto Stop</label>
                  <p className="text-white mt-1">{formatAbsoluteTime(timelapse.auto_stop_at)}</p>
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="overlays">
          <TimelapseOverlaySettings 
            timelapseId={timelapseId} 
            timelapseName={timelapse.name}
          />
        </TabsContent>

        <TabsContent value="settings" className="space-y-6">
          <div className="glass p-6 rounded-xl border border-purple-muted/30">
            <h3 className="text-lg font-semibold text-white mb-4">Timelapse Settings</h3>
            <div className="text-center py-8">
              <Settings className="w-12 h-12 mx-auto text-gray-500 mb-3" />
              <p className="text-muted-foreground">Settings panel coming soon</p>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
