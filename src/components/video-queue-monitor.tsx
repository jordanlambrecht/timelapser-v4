// src/components/video-queue-monitor.tsx
"use client"

import { useState } from "react"
import { useVideoQueue } from "@/hooks/use-video-automation"
import { useCaptureSettings } from "@/hooks/use-camera-countdown"
import { formatRelativeTime, formatAbsoluteTimeForCounter } from "@/lib/time-utils"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Separator } from "@/components/ui/separator"
import {
  Play,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Loader2,
  Calendar,
  Camera,
  Video,
  Trash2,
  RefreshCw,
  Target,
  Zap,
} from "lucide-react"
import { toast } from "@/lib/toast"
import { VideoQueueMonitorProps } from "@/types/video-automation"

export function VideoQueueMonitor({
  showHeader = true,
  maxJobs = 10,
  className = "",
}: VideoQueueMonitorProps) {
  const { status, jobs, isLoading, error, cancelJob, refresh } = useVideoQueue()
  const { timezone } = useCaptureSettings()
  const [selectedStatus, setSelectedStatus] = useState<string>("all")

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "pending":
        return <Clock className='h-4 w-4 text-orange-500' />
      case "processing":
        return <Loader2 className='h-4 w-4 text-blue-500 animate-spin' />
      case "completed":
        return <CheckCircle className='h-4 w-4 text-green-500' />
      case "failed":
        return <XCircle className='h-4 w-4 text-red-500' />
      case "cancelled":
        return <AlertCircle className='h-4 w-4 text-gray-500' />
      default:
        return <Clock className='h-4 w-4' />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "pending":
        return "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-200"
      case "processing":
        return "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200"
      case "completed":
        return "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200"
      case "failed":
        return "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200"
      case "cancelled":
        return "bg-gray-100 text-gray-800 dark:bg-gray-950 dark:text-gray-200"
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-950 dark:text-gray-200"
    }
  }

  const getTriggerIcon = (triggerType: string) => {
    switch (triggerType) {
      case "manual":
        return <Play className='h-3 w-3' />
      case "per_capture":
        return <Zap className='h-3 w-3' />
      case "scheduled":
        return <Calendar className='h-3 w-3' />
      case "milestone":
        return <Target className='h-3 w-3' />
      default:
        return <Video className='h-3 w-3' />
    }
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "high":
        return "text-red-600 dark:text-red-400"
      case "medium":
        return "text-yellow-600 dark:text-yellow-400"
      case "low":
        return "text-green-600 dark:text-green-400"
      default:
        return "text-gray-600 dark:text-gray-400"
    }
  }

  // Timezone-aware time formatting following AI-CONTEXT patterns
  const formatJobTime = (timestamp: string): { relative: string; absolute: string } => {
    const relative = formatRelativeTime(timestamp, {
      includeAbsolute: false,
      shortFormat: true,
      timezone,
    })
    
    const absolute = formatAbsoluteTimeForCounter(timestamp, timezone)
    
    return { relative, absolute }
  }

  const filteredJobs = jobs
    .filter((job) => selectedStatus === "all" || job.status === selectedStatus)
    .slice(0, maxJobs)

  const totalJobs =
    status.pending + status.processing + status.completed + status.failed
  const activeJobs = status.pending + status.processing

  const handleCancelJob = async (jobId: number) => {
    try {
      await cancelJob(jobId)
      toast.success("Video generation job cancelled")
    } catch (error) {
      // Error handling is done in the hook
    }
  }

  if (error) {
    return (
      <Card className={className}>
        <CardContent className='flex items-center justify-center py-8'>
          <div className='text-center space-y-2'>
            <AlertCircle className='h-8 w-8 text-red-500 mx-auto' />
            <p className='text-sm text-muted-foreground'>
              Failed to load queue data
            </p>
            <Button variant='outline' size='sm' onClick={refresh}>
              <RefreshCw className='h-3 w-3 mr-1' />
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className={className}>
      {showHeader && (
        <CardHeader>
          <div className='flex items-center justify-between'>
            <div className='flex items-center space-x-2'>
              <Video className='h-5 w-5' />
              <div>
                <CardTitle>Video Generation Queue</CardTitle>
                <CardDescription>
                  Monitor and manage automated video generation
                </CardDescription>
              </div>
            </div>
            <Button
              variant='outline'
              size='sm'
              onClick={refresh}
              disabled={isLoading}
            >
              <RefreshCw
                className={`h-3 w-3 mr-1 ${isLoading ? "animate-spin" : ""}`}
              />
              Refresh
            </Button>
          </div>
        </CardHeader>
      )}

      <CardContent className='space-y-6'>
        {/* Queue Statistics */}
        <div className='grid grid-cols-2 md:grid-cols-4 gap-4'>
          <div className='text-center p-3 bg-orange-50 dark:bg-orange-950/20 rounded-lg'>
            <div className='text-2xl font-bold text-orange-600 dark:text-orange-400'>
              {status.pending}
            </div>
            <p className='text-xs text-orange-700 dark:text-orange-300'>
              Pending
            </p>
          </div>

          <div className='text-center p-3 bg-blue-50 dark:bg-blue-950/20 rounded-lg'>
            <div className='text-2xl font-bold text-blue-600 dark:text-blue-400'>
              {status.processing}
            </div>
            <p className='text-xs text-blue-700 dark:text-blue-300'>
              Processing
            </p>
          </div>

          <div className='text-center p-3 bg-green-50 dark:bg-green-950/20 rounded-lg'>
            <div className='text-2xl font-bold text-green-600 dark:text-green-400'>
              {status.completed}
            </div>
            <p className='text-xs text-green-700 dark:text-green-300'>
              Completed
            </p>
          </div>

          <div className='text-center p-3 bg-red-50 dark:bg-red-950/20 rounded-lg'>
            <div className='text-2xl font-bold text-red-600 dark:text-red-400'>
              {status.failed}
            </div>
            <p className='text-xs text-red-700 dark:text-red-300'>Failed</p>
          </div>
        </div>

        {/* Queue Progress */}
        {totalJobs > 0 && (
          <div className='space-y-2'>
            <div className='flex items-center justify-between text-sm'>
              <span>Queue Progress</span>
              <span className='text-muted-foreground'>
                {totalJobs - activeJobs} / {totalJobs} completed
              </span>
            </div>
            <Progress
              value={
                totalJobs > 0 ? ((totalJobs - activeJobs) / totalJobs) * 100 : 0
              }
              className='h-2'
            />
          </div>
        )}

        {/* Filter Buttons */}
        <div className='flex flex-wrap gap-2'>
          {["all", "pending", "processing", "completed", "failed"].map(
            (statusFilter) => (
              <Button
                key={statusFilter}
                variant={
                  selectedStatus === statusFilter ? "default" : "outline"
                }
                size='sm'
                onClick={() => setSelectedStatus(statusFilter)}
                className='capitalize'
              >
                {statusFilter === "all" ? "All Jobs" : statusFilter}
              </Button>
            )
          )}
        </div>

        <Separator />

        {/* Job List */}
        <div className='space-y-3'>
          {isLoading ? (
            <div className='flex items-center justify-center py-8'>
              <Loader2 className='h-6 w-6 animate-spin' />
            </div>
          ) : filteredJobs.length === 0 ? (
            <div className='text-center py-8 text-muted-foreground'>
              <Video className='h-8 w-8 mx-auto mb-2 opacity-50' />
              <p className='text-sm'>
                {selectedStatus === "all"
                  ? "No jobs in queue"
                  : `No ${selectedStatus} jobs`}
              </p>
            </div>
          ) : (
            filteredJobs.map((job) => {
              // Get timezone-aware formatted times for this job
              const createdTime = formatJobTime(job.created_at)
              const startedTime = job.started_at ? formatJobTime(job.started_at) : null
              const completedTime = job.completed_at ? formatJobTime(job.completed_at) : null

              return (
                <div
                  key={job.id}
                  className='flex items-center justify-between p-3 border rounded-lg bg-card hover:bg-accent/50 transition-colors'
                >
                  <div className='flex items-center space-x-3 flex-1'>
                    {getStatusIcon(job.status)}

                    <div className='flex-1 min-w-0'>
                      <div className='flex items-center space-x-2 mb-1'>
                        <span className='font-medium truncate'>
                          {job.camera_name}
                        </span>
                        <Badge variant='outline' className='text-xs'>
                          {getTriggerIcon(job.trigger_type)}
                          <span className='ml-1 capitalize'>
                            {job.trigger_type.replace("_", " ")}
                          </span>
                        </Badge>
                        <Badge
                          variant='outline'
                          className={`text-xs ${getPriorityColor(job.priority)}`}
                        >
                          {job.priority}
                        </Badge>
                      </div>

                      {/* Timezone-aware time display following AI-CONTEXT patterns */}
                      <div className='text-xs text-muted-foreground space-y-1'>
                        <div>
                          <span>Created {createdTime.relative}</span>
                          {createdTime.absolute && (
                            <div className='text-xs text-muted-foreground/70'>
                              {createdTime.absolute}
                            </div>
                          )}
                        </div>
                        
                        {startedTime && (
                          <div>
                            <span>Started {startedTime.relative}</span>
                            {startedTime.absolute && (
                              <div className='text-xs text-muted-foreground/70'>
                                {startedTime.absolute}
                              </div>
                            )}
                          </div>
                        )}
                        
                        {completedTime && (
                          <div>
                            <span>Completed {completedTime.relative}</span>
                            {completedTime.absolute && (
                              <div className='text-xs text-muted-foreground/70'>
                                {completedTime.absolute}
                              </div>
                            )}
                          </div>
                        )}
                      </div>

                      {job.error_message && (
                        <div className='text-xs text-red-600 dark:text-red-400 mt-1'>
                          Error: {job.error_message}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className='flex items-center space-x-2'>
                    <Badge className={getStatusColor(job.status)}>
                      {job.status}
                    </Badge>

                    {(job.status === "pending" ||
                      job.status === "processing") && (
                      <Button
                        variant='ghost'
                        size='sm'
                        onClick={() => handleCancelJob(job.id)}
                        className='text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/20'
                      >
                        <Trash2 className='h-3 w-3' />
                      </Button>
                    )}
                  </div>
                </div>
              )
            })
          )}
        </div>

        {jobs.length > maxJobs && (
          <div className='text-center'>
            <p className='text-xs text-muted-foreground'>
              Showing {maxJobs} of {jobs.length} jobs
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
