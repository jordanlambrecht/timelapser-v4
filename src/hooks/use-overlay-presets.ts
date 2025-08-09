// src/hooks/use-overlay-presets.ts
"use client"

import { useState, useEffect } from "react"
import { toast } from "sonner"

// Modern overlay format interfaces
export interface OverlayItem {
  id: string
  type:
    | "date_time"
    | "frame_number"
    | "day_number"
    | "timelapse_name"
    | "custom_text"
    | "temperature"
    | "weather_conditions"
    | "weather"
    | "watermark"
  position: string
  enabled: boolean
  settings: any
}

export interface GlobalSettings {
  opacity: number
  font: string
  xMargin: number
  yMargin: number
  backgroundColor: string
  backgroundOpacity: number
  fillColor: string
  dropShadow: number
  preset?: string
}

export interface OverlayConfig {
  globalSettings: GlobalSettings
  overlayItems: OverlayItem[]
}

export interface OverlayPreset {
  id: number
  name: string
  description: string
  overlay_config: OverlayConfig
  is_builtin: boolean
  created_at: string
  updated_at: string
}

export interface OverlayPresetCreate {
  name: string
  description: string
  overlay_config: OverlayConfig
}

export interface UseOverlayPresetsReturn {
  presets: OverlayPreset[]
  loading: boolean
  error: string | null
  fetchPresets: () => Promise<void>
  refetch: () => Promise<void>
  createPreset: (preset: OverlayPresetCreate) => Promise<OverlayPreset | null>
  updatePreset: (
    id: number,
    preset: Partial<OverlayPresetCreate>
  ) => Promise<OverlayPreset | null>
  deletePreset: (id: number) => Promise<boolean>
}

export const useOverlayPresets = (): UseOverlayPresetsReturn => {
  const [presets, setPresets] = useState<OverlayPreset[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchPresets = async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await fetch("/api/overlays/presets")
      if (!response.ok) {
        throw new Error(`Failed to fetch presets: ${response.statusText}`)
      }

      const data = await response.json()
      setPresets(data)
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to fetch overlay presets"
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  const createPreset = async (
    preset: OverlayPresetCreate
  ): Promise<OverlayPreset | null> => {
    try {
      const response = await fetch("/api/overlays/presets", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(preset),
      })

      if (!response.ok) {
        throw new Error(`Failed to create preset: ${response.statusText}`)
      }

      const newPreset = await response.json()
      setPresets((prev) => [...prev, newPreset])
      toast.success("Overlay preset created successfully")
      return newPreset
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to create overlay preset"
      toast.error(errorMessage)
      return null
    }
  }

  const updatePreset = async (
    id: number,
    preset: Partial<OverlayPresetCreate>
  ): Promise<OverlayPreset | null> => {
    try {
      const response = await fetch(`/api/overlays/presets/${id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(preset),
      })

      if (!response.ok) {
        throw new Error(`Failed to update preset: ${response.statusText}`)
      }

      const updatedPreset = await response.json()
      setPresets((prev) => prev.map((p) => (p.id === id ? updatedPreset : p)))
      toast.success("Overlay preset updated successfully")
      return updatedPreset
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to update overlay preset"
      toast.error(errorMessage)
      return null
    }
  }

  const deletePreset = async (id: number): Promise<boolean> => {
    try {
      const response = await fetch(`/api/overlays/presets/${id}`, {
        method: "DELETE",
      })

      if (!response.ok) {
        throw new Error(`Failed to delete preset: ${response.statusText}`)
      }

      setPresets((prev) => prev.filter((p) => p.id !== id))
      toast.success("Overlay preset deleted successfully")
      return true
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to delete overlay preset"
      toast.error(errorMessage)
      return false
    }
  }

  const refetch = async () => {
    await fetchPresets()
  }

  useEffect(() => {
    fetchPresets()
  }, [])

  return {
    presets,
    loading,
    error,
    fetchPresets,
    refetch: fetchPresets,
    createPreset,
    updatePreset,
    deletePreset,
  }
}
