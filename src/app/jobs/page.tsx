"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useSSESubscription } from "@/contexts/sse-context"
import { RefreshCw, Clock, CheckCircle, XCircle, Loader2, Calendar, PlayCircle } from "lucide-react"
import { format } from "date-fns"

interface ScheduledJob {
  id: string
  job_type: string
  camera_id?: number
  camera_name?: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  scheduled_time: string
  start_time?: string
  end_time?: string
  error_message?: string
  progress?: number
  metadata?: Record<string, any>
}

interface ThumbnailStats {
  total_jobs_24h: number
  pending_jobs: number
  processing_jobs: number
  completed_jobs_24h: number
  failed_jobs_24h: number
  cancelled_jobs_24h: number
  avg_processing_time_ms: number
}

interface OverlayStats {
  total_jobs_24h: number
  pending_jobs: number
  processing_jobs: number
  completed_jobs_24h: number
  failed_jobs_24h: number
  cancelled_jobs_24h: number
  avg_processing_time_ms: number
}

interface JobsData {
  scheduled: ScheduledJob[]
  running: ScheduledJob[]
  recent: ScheduledJob[]
  stats: {
    total_scheduled: number
    total_running: number
    total_completed_today: number
    total_failed_today: number
  }
  thumbnail_stats: ThumbnailStats
  overlay_stats: OverlayStats
}

export default function JobsPage() {
  const [jobsData, setJobsData] = useState<JobsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Subscribe to job updates via SSE
  useSSESubscription(
    (event) => event.type === 'job_status_changed',
    (event) => {
      if (jobsData) {
        // Update job status in real-time
        const updatedJob = event.data.job
        setJobsData(prev => {
          if (!prev) return null
          
          // Update in appropriate list
          const updateList = (list: ScheduledJob[]) => 
            list.map(job => job.id === updatedJob.id ? updatedJob : job)
          
          return {
            ...prev,
            scheduled: updateList(prev.scheduled),
            running: updateList(prev.running),
            recent: updateList(prev.recent)
          }
        })
      }
    }
  )

  const fetchJobs = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await fetch('/api/jobs')
      if (!response.ok) throw new Error('Failed to fetch jobs')
      const data = await response.json()
      setJobsData(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchJobs()
    // Refresh every 30 seconds
    const interval = setInterval(fetchJobs, 30000)
    return () => clearInterval(interval)
  }, [])

  const getStatusBadge = (status: string) => {
    const variants: Record<string, { variant: "default" | "secondary" | "destructive" | "outline", icon: any }> = {
      pending: { variant: "outline", icon: Clock },
      running: { variant: "default", icon: Loader2 },
      completed: { variant: "secondary", icon: CheckCircle },
      failed: { variant: "destructive", icon: XCircle },
      cancelled: { variant: "outline", icon: XCircle }
    }
    
    const config = variants[status] || variants.pending
    const Icon = config.icon
    
    return (
      <Badge variant={config.variant} className="flex items-center gap-1">
        <Icon className={status === 'running' ? 'w-3 h-3 animate-spin' : 'w-3 h-3'} />
        {status}
      </Badge>
    )
  }

  const formatJobType = (type: string) => {
    return type.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ')
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-purple" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <p className="text-red-500">Error: {error}</p>
        <Button onClick={fetchJobs}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Retry
        </Button>
      </div>
    )
  }

  return (
    <div className="container mx-auto py-8 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Job Monitor</h1>
          <p className="text-muted-foreground mt-1">
            View and manage scheduled and running jobs
          </p>
        </div>
        <Button onClick={fetchJobs} variant="outline">
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Scheduled</CardDescription>
            <CardTitle className="text-2xl">
              {jobsData?.stats.total_scheduled || 0}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Running</CardDescription>
            <CardTitle className="text-2xl text-purple">
              {jobsData?.stats.total_running || 0}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Completed Today</CardDescription>
            <CardTitle className="text-2xl text-green-500">
              {jobsData?.stats.total_completed_today || 0}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Failed Today</CardDescription>
            <CardTitle className="text-2xl text-red-500">
              {jobsData?.stats.total_failed_today || 0}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Background Job Statistics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Thumbnail Job Statistics */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                <circle cx="8.5" cy="8.5" r="1.5"/>
                <polyline points="21,15 16,10 5,21"/>
              </svg>
              Thumbnail Generation
            </CardTitle>
            <CardDescription>
              Background thumbnail processing statistics
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Pending:</span>
                  <span className="font-medium text-yellow-600">
                    {jobsData?.thumbnail_stats?.pending_jobs || 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Processing:</span>
                  <span className="font-medium text-blue-600">
                    {jobsData?.thumbnail_stats?.processing_jobs || 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Completed (24h):</span>
                  <span className="font-medium text-green-600">
                    {jobsData?.thumbnail_stats?.completed_jobs_24h || 0}
                  </span>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Failed (24h):</span>
                  <span className="font-medium text-red-600">
                    {jobsData?.thumbnail_stats?.failed_jobs_24h || 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Total (24h):</span>
                  <span className="font-medium">
                    {jobsData?.thumbnail_stats?.total_jobs_24h || 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Avg Time:</span>
                  <span className="font-medium text-purple">
                    {jobsData?.thumbnail_stats?.avg_processing_time_ms 
                      ? `${Math.round(jobsData.thumbnail_stats.avg_processing_time_ms)}ms`
                      : '0ms'
                    }
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Overlay Job Statistics */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
              </svg>
              Overlay Generation
            </CardTitle>
            <CardDescription>
              Background overlay processing statistics
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Pending:</span>
                  <span className="font-medium text-yellow-600">
                    {jobsData?.overlay_stats?.pending_jobs || 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Processing:</span>
                  <span className="font-medium text-blue-600">
                    {jobsData?.overlay_stats?.processing_jobs || 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Completed (24h):</span>
                  <span className="font-medium text-green-600">
                    {jobsData?.overlay_stats?.completed_jobs_24h || 0}
                  </span>
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Failed (24h):</span>
                  <span className="font-medium text-red-600">
                    {jobsData?.overlay_stats?.failed_jobs_24h || 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Total (24h):</span>
                  <span className="font-medium">
                    {jobsData?.overlay_stats?.total_jobs_24h || 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Avg Time:</span>
                  <span className="font-medium text-purple">
                    {jobsData?.overlay_stats?.avg_processing_time_ms 
                      ? `${Math.round(jobsData.overlay_stats.avg_processing_time_ms)}ms`
                      : '0ms'
                    }
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Running Jobs */}
      {jobsData?.running && jobsData.running.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <PlayCircle className="w-5 h-5 text-purple" />
              Currently Running
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {jobsData.running.map(job => (
                <div key={job.id} className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{formatJobType(job.job_type)}</span>
                      {job.camera_name && (
                        <Badge variant="outline">{job.camera_name}</Badge>
                      )}
                    </div>
                    {job.start_time && (
                      <p className="text-sm text-muted-foreground">
                        Started: {format(new Date(job.start_time), 'HH:mm:ss')}
                      </p>
                    )}
                    {job.progress && (
                      <div className="w-48 h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-purple transition-all duration-300"
                          style={{ width: `${job.progress}%` }}
                        />
                      </div>
                    )}
                  </div>
                  {getStatusBadge(job.status)}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Scheduled Jobs */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="w-5 h-5" />
            Scheduled Jobs
          </CardTitle>
          <CardDescription>
            Upcoming jobs in the next 24 hours
          </CardDescription>
        </CardHeader>
        <CardContent>
          {jobsData?.scheduled && jobsData.scheduled.length > 0 ? (
            <div className="space-y-3">
              {jobsData.scheduled.map(job => (
                <div key={job.id} className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{formatJobType(job.job_type)}</span>
                      {job.camera_name && (
                        <Badge variant="outline">{job.camera_name}</Badge>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Scheduled: {format(new Date(job.scheduled_time), 'MMM dd, HH:mm:ss')}
                    </p>
                  </div>
                  {getStatusBadge(job.status)}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-center py-8">
              No scheduled jobs
            </p>
          )}
        </CardContent>
      </Card>

      {/* Recent Jobs */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Jobs</CardTitle>
          <CardDescription>
            Last 20 completed or failed jobs
          </CardDescription>
        </CardHeader>
        <CardContent>
          {jobsData?.recent && jobsData.recent.length > 0 ? (
            <div className="space-y-3">
              {jobsData.recent.map(job => (
                <div key={job.id} className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{formatJobType(job.job_type)}</span>
                      {job.camera_name && (
                        <Badge variant="outline">{job.camera_name}</Badge>
                      )}
                    </div>
                    <div className="flex gap-4 text-sm text-muted-foreground">
                      {job.end_time && (
                        <span>Completed: {format(new Date(job.end_time), 'MMM dd, HH:mm:ss')}</span>
                      )}
                      {job.start_time && job.end_time && (
                        <span>
                          Duration: {Math.round((new Date(job.end_time).getTime() - new Date(job.start_time).getTime()) / 1000)}s
                        </span>
                      )}
                    </div>
                    {job.error_message && (
                      <p className="text-sm text-red-500">{job.error_message}</p>
                    )}
                  </div>
                  {getStatusBadge(job.status)}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-center py-8">
              No recent jobs
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}