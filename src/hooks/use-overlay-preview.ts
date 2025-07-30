// src/hooks/use-overlay-preview.ts
"use client"

import { useState } from "react"
import { toast } from "sonner"

export interface OverlayPreviewRequest {
  camera_id: number
  overlay_config: {
    overlayPositions: Record<string, any>
    globalOptions: {
      opacity: number
      dropShadow?: number
      font: string
      xMargin: number
      yMargin: number
    }
  }
}

export interface OverlayPreviewResponse {
  image_path: string
  test_image_path: string
  success: boolean
  error_message?: string
}

export interface UseOverlayPreviewReturn {
  previewData: OverlayPreviewResponse | null
  isGenerating: boolean
  error: string | null
  generatePreview: (request: OverlayPreviewRequest) => Promise<OverlayPreviewResponse | null>
  clearPreview: () => void
}

export const useOverlayPreview = (): UseOverlayPreviewReturn => {
  const [previewData, setPreviewData] = useState<OverlayPreviewResponse | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const generatePreview = async (request: OverlayPreviewRequest): Promise<OverlayPreviewResponse | null> => {
    try {
      setIsGenerating(true)
      setError(null)
      
      console.log("Generating overlay preview for camera:", request.camera_id)
      
      const response = await fetch("/api/overlays/preview", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || `Failed to generate preview: ${response.statusText}`)
      }

      if (!data.success) {
        throw new Error(data.error_message || "Preview generation failed")
      }

      setPreviewData(data)
      toast.success("Overlay preview generated successfully")
      return data
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to generate overlay preview"
      setError(errorMessage)
      toast.error(errorMessage)
      return null
    } finally {
      setIsGenerating(false)
    }
  }

  const clearPreview = () => {
    setPreviewData(null)
    setError(null)
  }

  return {
    previewData,
    isGenerating,
    error,
    generatePreview,
    clearPreview,
  }
}