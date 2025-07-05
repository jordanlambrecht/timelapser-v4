// src/hooks/use-corruption-stats.ts
"use client"

import { useState, useEffect, useCallback } from "react"
import { useSSESubscription } from "@/contexts/sse-context"

interface CorruptionStats {
  total_cameras: number
  cameras_healthy: number
  cameras_monitoring: number
  cameras_degraded: number
  images_flagged_today: number
  images_flagged_week: number
  storage_saved_mb: number
  avg_processing_overhead_ms: number
  system_health_score: number
}

interface CameraCorruptionStats {
  lifetime_glitch_count: number
  recent_average_score: number
  consecutive_corruption_failures: number
  degraded_mode_active: boolean
  last_degraded_at: string | null
}

interface CorruptionLogEntry {
  id: number
  camera_id: number
  image_id: number | null
  corruption_score: number
  action_taken: string
  created_at: string
}

export function useCorruptionStats() {
  const [systemStats, setSystemStats] = useState<CorruptionStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchSystemStats = useCallback(async () => {
    try {
      setLoading(true)
      const response = await fetch("/api/corruption/stats")
      if (!response.ok) throw new Error("Failed to fetch corruption stats")

      const data = await response.json()
      setSystemStats(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSystemStats()
  }, [fetchSystemStats])

  // Listen for corruption events using SSE subscriptions
  useSSESubscription(
    (event) => event.type === "image_corruption_detected",
    useCallback(() => {
      // 🚨 ARCHITECTURAL ISSUE: Should use React Query cache invalidation instead of manual fetch
      // TODO: Convert to React Query pattern when this hook is refactored
      fetchSystemStats()
    }, [fetchSystemStats])
  )

  useSSESubscription(
    (event) => event.type === "camera_degraded_mode_triggered",
    useCallback(() => {
      // 🚨 ARCHITECTURAL ISSUE: Should use React Query cache invalidation instead of manual fetch
      fetchSystemStats()
    }, [fetchSystemStats])
  )

  useSSESubscription(
    (event) => event.type === "camera_corruption_reset",
    useCallback(() => {
      // 🚨 ARCHITECTURAL ISSUE: Should use React Query cache invalidation instead of manual fetch
      fetchSystemStats()
    }, [fetchSystemStats])
  )

  return {
    systemStats,
    loading,
    error,
    refetch: fetchSystemStats,
  }
}

export function useCameraCorruptionStats(cameraId: number) {
  const [stats, setStats] = useState<CameraCorruptionStats | null>(null)
  const [recentIssues, setRecentIssues] = useState<any[]>([])
  const [qualityTrend, setQualityTrend] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchCameraStats = useCallback(async () => {
    try {
      setLoading(true)
      const response = await fetch(`/api/corruption/camera/${cameraId}/stats`)
      if (!response.ok)
        throw new Error("Failed to fetch camera corruption stats")

      const data = await response.json()
      setStats(data.camera_stats)
      setRecentIssues(data.recent_issues)
      setQualityTrend(data.quality_trend)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error")
    } finally {
      setLoading(false)
    }
  }, [cameraId])

  useEffect(() => {
    fetchCameraStats()
  }, [fetchCameraStats])

  // Listen for camera-specific corruption events using SSE subscriptions
  useSSESubscription(
    (event) =>
      event.type === "image_corruption_detected" &&
      event.data?.camera_id === cameraId,
    useCallback(() => {
      fetchCameraStats()
    }, [fetchCameraStats])
  )

  useSSESubscription(
    (event) =>
      event.type === "camera_degraded_mode_triggered" &&
      event.data?.camera_id === cameraId,
    useCallback(() => {
      fetchCameraStats()
    }, [fetchCameraStats])
  )

  useSSESubscription(
    (event) =>
      event.type === "camera_corruption_reset" &&
      event.data?.camera_id === cameraId,
    useCallback(() => {
      fetchCameraStats()
    }, [fetchCameraStats])
  )

  const resetDegradedMode = useCallback(async () => {
    try {
      const response = await fetch(
        `/api/corruption/camera/${cameraId}/reset-degraded`,
        {
          method: "POST",
        }
      )
      if (!response.ok) throw new Error("Failed to reset degraded mode")

      // Refresh stats after reset
      await fetchCameraStats()
    } catch (err) {
      throw new Error(err instanceof Error ? err.message : "Unknown error")
    }
  }, [cameraId, fetchCameraStats])

  return {
    stats,
    recentIssues,
    qualityTrend,
    loading,
    error,
    refetch: fetchCameraStats,
    resetDegradedMode,
  }
}

export function useCorruptionLogs(cameraId?: number) {
  const [logs, setLogs] = useState<CorruptionLogEntry[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchLogs = useCallback(
    async (page: number = 1, limit: number = 50) => {
      try {
        setLoading(true)
        const params = new URLSearchParams({
          page: page.toString(),
          limit: limit.toString(),
          offset: ((page - 1) * limit).toString(),
        })

        if (cameraId) params.append("camera_id", cameraId.toString())

        const response = await fetch(`/api/corruption/logs?${params}`)
        if (!response.ok) throw new Error("Failed to fetch corruption logs")

        const data = await response.json()
        setLogs(data.logs)
        setTotalCount(data.total_count)
        setCurrentPage(page)
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error")
      } finally {
        setLoading(false)
      }
    },
    [cameraId]
  )

  useEffect(() => {
    fetchLogs(1)
  }, [fetchLogs])

  const loadPage = useCallback(
    (page: number) => {
      fetchLogs(page)
    },
    [fetchLogs]
  )

  return {
    logs,
    totalCount,
    currentPage,
    loading,
    error,
    loadPage,
    refetch: () => fetchLogs(currentPage),
  }
}

export function useCorruptionActions() {
  const resetCameraDegradedMode = useCallback(async (cameraId: number) => {
    try {
      const response = await fetch(
        `/api/corruption/camera/${cameraId}/reset-degraded`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        }
      )

      if (!response.ok) {
        throw new Error("Failed to reset camera degraded mode")
      }

      return await response.json()
    } catch (err) {
      throw err
    }
  }, [])

  return {
    resetCameraDegradedMode,
  }
}
