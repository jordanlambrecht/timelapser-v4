"use client"

import { useState, useEffect, useCallback } from "react"
import {
  VideoQueueStatus,
  VideoGenerationJob,
  AutomationStats,
  TimelapseAutomationSettings,
  ManualTriggerRequest,
} from "@/types/video-automation"
import { toast } from "@/lib/toast"
import { useSSESubscription } from "@/contexts/sse-context"

interface VideoJobEventData {
  job_id?: number
  status?: string
  camera_id?: number
  [key: string]: any
}

export function useVideoQueue() {
  const [status, setStatus] = useState<VideoQueueStatus>({
    pending: 0,
    processing: 0,
    completed: 0,
    failed: 0,
  })
  const [jobs, setJobs] = useState<VideoGenerationJob[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchQueueStatus = async () => {
    try {
      const response = await fetch("/api/video-automation/queue/status")
      if (!response.ok) throw new Error("Failed to fetch queue status")

      const data = await response.json()
      setStatus(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error")
      console.error("Error fetching queue status:", err)
    }
  }

  const fetchJobs = async (statusFilter?: string, limit: number = 50) => {
    try {
      setIsLoading(true)
      const params = new URLSearchParams()
      if (statusFilter) params.append("status", statusFilter)
      params.append("limit", limit.toString())

      const response = await fetch(`/api/video-automation/queue/jobs?${params}`)
      if (!response.ok) throw new Error("Failed to fetch jobs")

      const data = await response.json()
      setJobs(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error")
      console.error("Error fetching jobs:", err)
    } finally {
      setIsLoading(false)
    }
  }

  // ✅ SSE COMPLIANCE: Use centralized SSE system instead of polling
  // Subscribe to video job events following AI-CONTEXT rules
  useSSESubscription<VideoJobEventData>(
    (event) =>
      event.type === "video_job_queued" ||
      event.type === "video_job_started" ||
      event.type === "video_job_completed" ||
      event.type === "video_job_failed" ||
      event.type === "video_job_cancelled",
    useCallback((event) => {
      // Real-time updates when video jobs change status
      // This replaces the 30-second polling interval
      fetchQueueStatus()

      // For job list updates, we could be more granular but refetching is safe
      if (event.type === "video_job_queued") {
        fetchJobs() // New job added, refresh list
      }
    }, []),
    []
  )

  const triggerManualVideo = async (request: ManualTriggerRequest) => {
    try {
      const response = await fetch("/api/video-automation/trigger/manual", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(
          errorData.detail || "Failed to trigger video generation"
        )
      }

      const result = await response.json()
      toast.success(`Video generation started: ${result.message}`)

      // Refresh queue data
      await Promise.all([fetchQueueStatus(), fetchJobs()])

      return result
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "Failed to trigger video generation"
      toast.error(message)
      throw err
    }
  }

  const cancelJob = async (jobId: number) => {
    try {
      const response = await fetch(
        `/api/video-automation/queue/jobs/${jobId}`,
        {
          method: "DELETE",
        }
      )

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || "Failed to cancel job")
      }

      toast.success("Job cancelled successfully")

      // Refresh data
      await Promise.all([fetchQueueStatus(), fetchJobs()])
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to cancel job"
      toast.error(message)
      throw err
    }
  }

  // Initial load
  useEffect(() => {
    Promise.all([fetchQueueStatus(), fetchJobs()])
  }, [])

  return {
    status,
    jobs,
    isLoading,
    error,
    fetchQueueStatus,
    fetchJobs,
    triggerManualVideo,
    cancelJob,
    refresh: () => Promise.all([fetchQueueStatus(), fetchJobs()]),
  }
}

export function useAutomationStats() {
  const [stats, setStats] = useState<AutomationStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStats = async () => {
    try {
      setIsLoading(true)
      const response = await fetch("/api/video-automation/stats")
      if (!response.ok) throw new Error("Failed to fetch automation stats")

      const data = await response.json()
      setStats(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error")
      console.error("Error fetching automation stats:", err)
    } finally {
      setIsLoading(false)
    }
  }

  // Subscribe to automation stats changes
  useSSESubscription<any>(
    (event) => event.type === "automation_stats_updated",
    useCallback((event) => {
      // Real-time stats updates - replaces 2-minute polling
      fetchStats()
    }, []),
    []
  )

  useEffect(() => {
    fetchStats()
  }, [])

  return { stats, isLoading, error, refresh: fetchStats }
}

// Camera automation settings hook removed per architecture decision:
// Automation settings now only exist at timelapse level for cleaner design

export function useTimelapseAutomation(timelapseId: number) {
  const [settings, setSettings] = useState<TimelapseAutomationSettings | null>(
    null
  )
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchSettings = async () => {
    try {
      setIsLoading(true)
      const response = await fetch(
        `/api/video-automation/timelapse/${timelapseId}/settings`
      )
      if (!response.ok)
        throw new Error("Failed to fetch timelapse automation settings")

      const data = await response.json()
      setSettings(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error")
      console.error("Error fetching timelapse automation settings:", err)
    } finally {
      setIsLoading(false)
    }
  }

  const updateSettings = async (newSettings: TimelapseAutomationSettings) => {
    try {
      const response = await fetch(
        `/api/video-automation/timelapse/${timelapseId}/settings`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(newSettings),
        }
      )

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(
          errorData.detail || "Failed to update automation settings"
        )
      }

      const result = await response.json()
      setSettings(newSettings)
      toast.success("Timelapse automation settings updated")

      return result
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to update settings"
      toast.error(message)
      throw err
    }
  }

  useEffect(() => {
    if (timelapseId) {
      fetchSettings()
    }
  }, [timelapseId])

  return {
    settings,
    isLoading,
    error,
    updateSettings,
    refresh: fetchSettings,
  }
}
