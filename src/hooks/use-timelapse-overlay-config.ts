// src/hooks/use-timelapse-overlay-config.ts
"use client"

import { useState, useEffect } from "react"
import { toast } from "sonner"
import type { OverlayConfig } from "@/hooks/use-overlay-presets"

export interface TimelapseOverlayConfig {
  timelapse_id: number
  overlay_config: OverlayConfig
  created_at: string
  updated_at: string
}

export interface OverlayConfigCreate {
  overlay_config: OverlayConfig
}

export interface UseTimelapseOverlayConfigReturn {
  config: TimelapseOverlayConfig | null
  loading: boolean
  error: string | null
  fetchConfig: () => Promise<void>
  createConfig: (
    config: OverlayConfigCreate
  ) => Promise<TimelapseOverlayConfig | null>
  updateConfig: (
    config: OverlayConfigCreate
  ) => Promise<TimelapseOverlayConfig | null>
  deleteConfig: () => Promise<boolean>
  hasConfig: boolean
}

export const useTimelapseOverlayConfig = (
  timelapseId: number
): UseTimelapseOverlayConfigReturn => {
  const [config, setConfig] = useState<TimelapseOverlayConfig | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchConfig = async () => {
    if (!timelapseId) return

    try {
      setLoading(true)
      setError(null)

      const response = await fetch(`/api/timelapses/${timelapseId}/overlays`)

      if (response.status === 404) {
        // No config exists for this timelapse
        setConfig(null)
        return
      }

      if (!response.ok) {
        throw new Error(
          `Failed to fetch overlay config: ${response.statusText}`
        )
      }

      const data = await response.json()
      setConfig(data)
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : "Failed to fetch overlay configuration"
      setError(errorMessage)
      console.error("Error fetching overlay config:", err)
    } finally {
      setLoading(false)
    }
  }

  const createConfig = async (
    configData: OverlayConfigCreate
  ): Promise<TimelapseOverlayConfig | null> => {
    if (!timelapseId) return null

    try {
      const response = await fetch(`/api/timelapses/${timelapseId}/overlays`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(configData),
      })

      if (!response.ok) {
        const errorData = await response
          .json()
          .catch(() => ({ error: "Unknown error" }))
        throw new Error(
          errorData.error ||
            `Failed to create overlay config: ${response.statusText}`
        )
      }

      const newConfig = await response.json()
      setConfig(newConfig)
      toast.success("Overlay configuration created successfully")
      return newConfig
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : "Failed to create overlay configuration"
      setError(errorMessage)
      toast.error(errorMessage)
      return null
    }
  }

  const updateConfig = async (
    configData: OverlayConfigCreate
  ): Promise<TimelapseOverlayConfig | null> => {
    if (!timelapseId) return null

    try {
      const response = await fetch(`/api/timelapses/${timelapseId}/overlays`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(configData),
      })

      if (!response.ok) {
        const errorData = await response
          .json()
          .catch(() => ({ error: "Unknown error" }))
        throw new Error(
          errorData.error ||
            `Failed to update overlay config: ${response.statusText}`
        )
      }

      const updatedConfig = await response.json()
      setConfig(updatedConfig)
      toast.success("Overlay configuration updated successfully")
      return updatedConfig
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : "Failed to update overlay configuration"
      setError(errorMessage)
      toast.error(errorMessage)
      return null
    }
  }

  const deleteConfig = async (): Promise<boolean> => {
    if (!timelapseId) return false

    try {
      const response = await fetch(`/api/timelapses/${timelapseId}/overlays`, {
        method: "DELETE",
      })

      if (!response.ok) {
        const errorData = await response
          .json()
          .catch(() => ({ error: "Unknown error" }))
        throw new Error(
          errorData.error ||
            `Failed to delete overlay config: ${response.statusText}`
        )
      }

      setConfig(null)
      toast.success("Overlay configuration deleted successfully")
      return true
    } catch (err) {
      const errorMessage =
        err instanceof Error
          ? err.message
          : "Failed to delete overlay configuration"
      setError(errorMessage)
      toast.error(errorMessage)
      return false
    }
  }

  // Load config when component mounts or timelapseId changes
  useEffect(() => {
    if (timelapseId) {
      fetchConfig()
    }
  }, [timelapseId])

  return {
    config,
    loading,
    error,
    fetchConfig,
    createConfig,
    updateConfig,
    deleteConfig,
    hasConfig: config !== null,
  }
}
