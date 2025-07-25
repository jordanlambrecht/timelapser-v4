// src/hooks/use-timelapse-library.ts
"use client"

import { useState, useEffect, useCallback } from "react"
import { toast } from "@/lib/toast"
import type { Timelapse } from "@/types/timelapses"

export interface TimelapseLibraryStatistics {
  total_timelapses: number
  starred_count: number
  active_count: number
  total_images: number
  total_storage_bytes: number
  oldest_timelapse_date?: string
}

export interface TimelapseForLibrary extends Timelapse {
  camera_name: string
  latest_image_path?: string
  video_count: number
  starred?: boolean
  is_active: boolean
}

export interface UseTimelapseLibraryOptions {
  sortBy: "camera" | "alphabetical" | "chronological"
  sortOrder: "asc" | "desc"
  starredOnly: boolean
  includeActive: boolean
}

export interface UseTimelapseLibraryResult {
  timelapses: TimelapseForLibrary[]
  statistics: TimelapseLibraryStatistics | null
  loading: boolean
  error: string | null
  statisticsError: boolean
  refetch: () => Promise<void>
  updateTimelapse: (id: number, updates: Partial<TimelapseForLibrary>) => void
}

export function useTimelapseLibrary(
  options: UseTimelapseLibraryOptions
): UseTimelapseLibraryResult {
  const [timelapses, setTimelapses] = useState<TimelapseForLibrary[]>([])
  const [statistics, setStatistics] = useState<TimelapseLibraryStatistics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statisticsError, setStatisticsError] = useState(false)

  const fetchLibraryData = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      setStatisticsError(false)

      // Build query parameters
      const params = new URLSearchParams({
        sort: options.sortBy,
        order: options.sortOrder,
        include_active: options.includeActive.toString(),
      })

      if (options.starredOnly) {
        params.set("starred_only", "true")
      }

      // Fetch timelapses with enhanced data for library view
      const timelapsesResponse = await fetch(`/api/timelapses?${params}`)
      if (!timelapsesResponse.ok) {
        throw new Error(`Failed to fetch timelapses: ${timelapsesResponse.status}`)
      }

      const timelapsesData = await timelapsesResponse.json()

      // Transform the data for library use
      const timelapsesList: TimelapseForLibrary[] = timelapsesData.data?.map((timelapse: any) => ({
        ...timelapse,
        is_active: timelapse.status === "running" || timelapse.status === "paused",
        starred: timelapse.starred || false,
        video_count: timelapse.video_count || 0,
        camera_name: timelapse.camera_name || "Unknown Camera",
        latest_image_path: timelapse.latest_image_path,
      })) || []

      setTimelapses(timelapsesList)

      // Fetch statistics separately with error handling
      try {
        const statsResponse = await fetch("/api/timelapses/statistics")
        if (statsResponse.ok) {
          const statsData = await statsResponse.json()
          setStatistics(statsData.data || null)
        } else {
          console.warn(`Failed to fetch statistics: ${statsResponse.status}`)
          setStatistics(null)
          setStatisticsError(true)
        }
      } catch (statsError) {
        console.warn("Error fetching statistics:", statsError)
        setStatistics(null)
        setStatisticsError(true)
        // Don't show toast for statistics errors since the main page still works
      }

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch library data"
      setError(errorMessage)
      toast.error("Failed to load timelapse library", {
        description: errorMessage,
      })
    } finally {
      setLoading(false)
    }
  }, [options])

  // Optimistic update function for immediate UI feedback
  const updateTimelapse = useCallback((id: number, updates: Partial<TimelapseForLibrary>) => {
    setTimelapses(prev => 
      prev.map(timelapse => 
        timelapse.id === id 
          ? { ...timelapse, ...updates }
          : timelapse
      )
    )
  }, [])

  useEffect(() => {
    fetchLibraryData()
  }, [options.sortBy, options.sortOrder, options.starredOnly, options.includeActive])

  return {
    timelapses,
    statistics,
    loading,
    error,
    statisticsError,
    refetch: fetchLibraryData,
    updateTimelapse,
  }
}
