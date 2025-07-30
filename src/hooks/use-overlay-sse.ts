// src/hooks/use-overlay-sse.ts
"use client"

import { useEffect, useState } from "react"
import { useSSE } from "@/contexts/sse-context"
import { toast } from "sonner"

export interface OverlaySSEEvent {
  type: 'overlay_generation_started' | 'overlay_generated' | 'overlay_generation_failed' | 'overlay_preview_started' | 'overlay_preview_generated' | 'overlay_preview_failed'
  image_id?: number
  timelapse_id?: number
  camera_id?: number
  overlay_path?: string
  preview_path?: string
  test_image_path?: string
  error?: string
  force_regenerate?: boolean
  timestamp: string
}

export interface UseOverlaySSEReturn {
  lastOverlayEvent: OverlaySSEEvent | null
  overlayGenerationInProgress: Set<number>
  previewGenerationInProgress: Set<number>
  generationErrors: Map<number, string>
}

export const useOverlaySSE = (): UseOverlaySSEReturn => {
  const { subscribe } = useSSE()
  const [lastOverlayEvent, setLastOverlayEvent] = useState<OverlaySSEEvent | null>(null)
  const [overlayGenerationInProgress, setOverlayGenerationInProgress] = useState<Set<number>>(new Set())
  const [previewGenerationInProgress, setPreviewGenerationInProgress] = useState<Set<number>>(new Set())
  const [generationErrors, setGenerationErrors] = useState<Map<number, string>>(new Map())

  useEffect(() => {
    const unsubscribe = subscribe((event) => {
      // Filter overlay-related events
      if (event.type?.includes('overlay')) {
        const overlayEvent = event as OverlaySSEEvent
        setLastOverlayEvent(overlayEvent)

        // Handle overlay generation events
        switch (overlayEvent.type) {
          case 'overlay_generation_started':
            if (overlayEvent.image_id) {
              setOverlayGenerationInProgress(prev => new Set(prev).add(overlayEvent.image_id!))
              setGenerationErrors(prev => {
                const newMap = new Map(prev)
                newMap.delete(overlayEvent.image_id!)
                return newMap
              })
            }
            break

          case 'overlay_generated':
            if (overlayEvent.image_id) {
              setOverlayGenerationInProgress(prev => {
                const newSet = new Set(prev)
                newSet.delete(overlayEvent.image_id!)
                return newSet
              })
              
              // Show success toast for manual/priority overlays
              if (overlayEvent.force_regenerate) {
                toast.success(`Overlay generated for image ${overlayEvent.image_id}`, {
                  description: overlayEvent.overlay_path ? `Saved to ${overlayEvent.overlay_path}` : undefined
                })
              }
            }
            break

          case 'overlay_generation_failed':
            if (overlayEvent.image_id) {
              setOverlayGenerationInProgress(prev => {
                const newSet = new Set(prev)
                newSet.delete(overlayEvent.image_id!)
                return newSet
              })
              
              const errorMessage = overlayEvent.error || 'Unknown error'
              setGenerationErrors(prev => new Map(prev).set(overlayEvent.image_id!, errorMessage))
              
              toast.error(`Failed to generate overlay for image ${overlayEvent.image_id}`, {
                description: errorMessage
              })
            }
            break

          case 'overlay_preview_started':
            if (overlayEvent.camera_id) {
              setPreviewGenerationInProgress(prev => new Set(prev).add(overlayEvent.camera_id!))
            }
            break

          case 'overlay_preview_generated':
            if (overlayEvent.camera_id) {
              setPreviewGenerationInProgress(prev => {
                const newSet = new Set(prev)
                newSet.delete(overlayEvent.camera_id!)
                return newSet
              })
              
              toast.success(`Overlay preview generated for camera ${overlayEvent.camera_id}`, {
                description: overlayEvent.preview_path ? `Preview saved` : undefined
              })
            }
            break

          case 'overlay_preview_failed':
            if (overlayEvent.camera_id) {
              setPreviewGenerationInProgress(prev => {
                const newSet = new Set(prev)
                newSet.delete(overlayEvent.camera_id!)
                return newSet
              })
              
              toast.error(`Failed to generate overlay preview for camera ${overlayEvent.camera_id}`, {
                description: overlayEvent.error || 'Unknown error'
              })
            }
            break
        }
      }
    })

    return unsubscribe
  }, [subscribe])

  return {
    lastOverlayEvent,
    overlayGenerationInProgress,
    previewGenerationInProgress,
    generationErrors,
  }
}