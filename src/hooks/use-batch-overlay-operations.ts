// src/hooks/use-batch-overlay-operations.ts
"use client"

import { useState } from "react"
import { toast } from "sonner"

export interface BatchOverlayResult {
  success: number[]
  failed: { id: number; error: string }[]
}

export interface UseBatchOverlayOperationsReturn {
  isProcessing: boolean
  processingProgress: number
  reprocessOverlays: (timelapseIds: number[]) => Promise<BatchOverlayResult>
}

export const useBatchOverlayOperations = (): UseBatchOverlayOperationsReturn => {
  const [isProcessing, setIsProcessing] = useState(false)
  const [processingProgress, setProcessingProgress] = useState(0)

  const reprocessOverlays = async (timelapseIds: number[]): Promise<BatchOverlayResult> => {
    if (timelapseIds.length === 0) {
      return { success: [], failed: [] }
    }

    setIsProcessing(true)
    setProcessingProgress(0)
    
    const results: BatchOverlayResult = {
      success: [],
      failed: []
    }

    try {
      for (let i = 0; i < timelapseIds.length; i++) {
        const timelapseId = timelapseIds[i]
        
        try {
          const response = await fetch(`/api/timelapses/${timelapseId}/overlays/reprocess`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            }
          })

          if (response.ok) {
            results.success.push(timelapseId)
            toast.success(`Started overlay reprocessing for timelapse ${timelapseId}`)
          } else {
            const errorData = await response.json().catch(() => ({ error: "Unknown error" }))
            results.failed.push({
              id: timelapseId,
              error: errorData.error || `HTTP ${response.status}`
            })
            toast.error(`Failed to start overlay reprocessing for timelapse ${timelapseId}`)
          }
        } catch (error) {
          results.failed.push({
            id: timelapseId,
            error: error instanceof Error ? error.message : "Network error"
          })
          toast.error(`Network error for timelapse ${timelapseId}`)
        }

        // Update progress
        setProcessingProgress(((i + 1) / timelapseIds.length) * 100)
      }

      // Show summary
      if (results.success.length > 0) {
        toast.success(
          `Overlay reprocessing started for ${results.success.length} timelapse${results.success.length !== 1 ? 's' : ''}`,
          {
            description: results.failed.length > 0 ? 
              `${results.failed.length} failed to start` : 
              "Check real-time updates for progress"
          }
        )
      }

      if (results.failed.length > 0 && results.success.length === 0) {
        toast.error(`Failed to start overlay reprocessing for all ${results.failed.length} timelapse${results.failed.length !== 1 ? 's' : ''}`)
      }

    } finally {
      setIsProcessing(false)
      setProcessingProgress(0)
    }

    return results
  }

  return {
    isProcessing,
    processingProgress,
    reprocessOverlays
  }
}