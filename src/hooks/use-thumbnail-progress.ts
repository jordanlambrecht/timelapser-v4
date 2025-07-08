"use client"

import { useState, useCallback } from "react"
import { useSSESubscription } from "@/contexts/sse-context"
import { toast } from "@/lib/toast"

interface ThumbnailProgressState {
  isActive: boolean
  totalJobs: number
  completedJobs: number
  failedJobs: number
}

interface UseThumbnailProgressOptions {
  timelapseId?: number
  onComplete?: () => void
  onError?: (error: string) => void
}

export function useThumbnailProgress(
  options: UseThumbnailProgressOptions = {}
) {
  const { timelapseId, onComplete, onError } = options

  const [progress, setProgress] = useState<ThumbnailProgressState>({
    isActive: false,
    totalJobs: 0,
    completedJobs: 0,
    failedJobs: 0,
  })

  const resetProgress = useCallback(() => {
    setProgress({
      isActive: false,
      totalJobs: 0,
      completedJobs: 0,
      failedJobs: 0,
    })
  }, [])

  const startTracking = useCallback((totalJobs: number) => {
    setProgress({
      isActive: true,
      totalJobs,
      completedJobs: 0,
      failedJobs: 0,
    })
  }, [])

  // SSE subscription for thumbnail events
  useSSESubscription(
    (event) => {
      // Listen for thumbnail job events related to this timelapse (if specified)
      const isRelevantEvent =
        !timelapseId || event.data?.timelapse_id === timelapseId

      return (
        isRelevantEvent &&
        (event.type === "thumbnail_job_completed" ||
          event.type === "thumbnail_bulk_queued" ||
          event.type === "thumbnail_job_failed_permanently" ||
          event.type === "thumbnail_regeneration_started" ||
          event.type === "thumbnail_regeneration_cancelled")
      )
    },
    (event) => {
      if (event.type === "thumbnail_bulk_queued") {
        // Start tracking progress
        const totalJobs = event.data.total_jobs || 0
        startTracking(totalJobs)

        toast.info(`Processing ${totalJobs} thumbnail jobs...`, {
          duration: 3000,
        })
      } else if (event.type === "thumbnail_job_completed") {
        // Update progress
        setProgress((prev) => {
          const newCompleted = prev.completedJobs + 1
          const newProgress = { ...prev, completedJobs: newCompleted }

          // Check if all jobs are complete
          if (
            prev.isActive &&
            prev.totalJobs > 0 &&
            newCompleted >= prev.totalJobs
          ) {
            // All jobs completed
            const finalProgress = { ...newProgress, isActive: false }

            toast.success(
              `Thumbnail regeneration completed! Generated ${newCompleted} thumbnails.`,
              {
                duration: 5000,
              }
            )

            // Call completion callback
            onComplete?.()

            return finalProgress
          } else if (prev.isActive && prev.totalJobs > 0) {
            // Show progress update
            const progressPercent = Math.round(
              (newCompleted / prev.totalJobs) * 100
            )
            toast.info(
              `Progress: ${newCompleted}/${prev.totalJobs} thumbnails (${progressPercent}%)`,
              {
                duration: 2000,
              }
            )
          }

          return newProgress
        })
      } else if (event.type === "thumbnail_job_failed_permanently") {
        // Track failed job
        setProgress((prev) => {
          const newFailed = prev.failedJobs + 1
          const totalProcessed = prev.completedJobs + newFailed
          const newProgress = { ...prev, failedJobs: newFailed }

          // Show error toast
          toast.warning(
            `Failed to generate thumbnail for image ${event.data.image_id}`,
            {
              duration: 4000,
            }
          )

          // Check if all jobs are done (including failures)
          if (
            prev.isActive &&
            prev.totalJobs > 0 &&
            totalProcessed >= prev.totalJobs
          ) {
            const finalProgress = { ...newProgress, isActive: false }

            toast.info("Thumbnail regeneration completed with some failures.", {
              duration: 5000,
            })

            // Call error callback if there were failures
            if (newFailed > 0) {
              onError?.(`${newFailed} thumbnail jobs failed`)
            } else {
              onComplete?.()
            }

            return finalProgress
          }

          return newProgress
        })
      } else if (event.type === "thumbnail_regeneration_started") {
        // Global regeneration started
        toast.info("Global thumbnail regeneration started", {
          duration: 3000,
        })
      } else if (event.type === "thumbnail_regeneration_cancelled") {
        // Global regeneration cancelled
        resetProgress()
        toast.warning("Thumbnail regeneration cancelled", {
          duration: 3000,
        })
      }
    },
    [timelapseId, onComplete, onError, startTracking]
  )

  const progressPercent =
    progress.totalJobs > 0
      ? Math.round(
          ((progress.completedJobs + progress.failedJobs) /
            progress.totalJobs) *
            100
        )
      : 0

  return {
    progress,
    progressPercent,
    isActive: progress.isActive,
    startTracking,
    resetProgress,
  }
}
