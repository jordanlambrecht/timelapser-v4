"use client"

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  ReactNode,
} from "react"
import { parseCaptureInterval } from "@/lib/time-utils"

interface SettingsContextType {
  // Core settings
  captureInterval: number
  timezone: string
  generateThumbnails: boolean
  imageCaptureType: "PNG" | "JPG"

  // Loading states
  loading: boolean
  error: string | null

  // Actions
  updateSetting: (key: string, value: any) => Promise<boolean>
  refetch: () => Promise<void>
}

const SettingsContext = createContext<SettingsContextType | undefined>(
  undefined
)

interface SettingsProviderProps {
  children: ReactNode
}

export function SettingsProvider({ children }: SettingsProviderProps) {
  const [settings, setSettings] = useState({
    captureInterval: 300,
    timezone: "America/Chicago",
    generateThumbnails: true,
    imageCaptureType: "JPG" as const,
  })

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastFetch, setLastFetch] = useState(0)

  const fetchSettings = useCallback(
    async (force = false) => {
      const now = Date.now()
      // Cache for 5 minutes unless forced
      if (!force && now - lastFetch < 300000 && !loading) return

      try {
        setError(null)
        const response = await fetch("/api/settings")
        if (!response.ok) {
          throw new Error(`Settings fetch failed: ${response.status}`)
        }

        const data = await response.json()

        setSettings({
          captureInterval: parseCaptureInterval(data.capture_interval),
          timezone: data.timezone || "America/Chicago",
          generateThumbnails: data.generate_thumbnails !== false,
          imageCaptureType: data.image_capture_type || "JPG",
        })

        setLastFetch(now)
      } catch (err) {
        console.error("Failed to fetch settings:", err)
        setError(err instanceof Error ? err.message : "Unknown error")
      } finally {
        setLoading(false)
      }
    },
    [lastFetch, loading]
  )

  const updateSetting = useCallback(
    async (key: string, value: any): Promise<boolean> => {
      try {
        const response = await fetch("/api/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ [key]: value }),
        })

        if (!response.ok) {
          throw new Error(`Settings update failed: ${response.status}`)
        }

        // Update local state
        setSettings((prev) => ({
          ...prev,
          [key]:
            key === "captureInterval" ? parseCaptureInterval(value) : value,
        }))

        return true
      } catch (err) {
        console.error("Failed to update setting:", err)
        setError(err instanceof Error ? err.message : "Update failed")
        return false
      }
    },
    []
  )

  useEffect(() => {
    fetchSettings()
  }, [fetchSettings])

  const value: SettingsContextType = {
    ...settings,
    loading,
    error,
    updateSetting,
    refetch: () => fetchSettings(true),
  }

  return (
    <SettingsContext.Provider value={value}>
      {children}
    </SettingsContext.Provider>
  )
}

export function useSettings() {
  const context = useContext(SettingsContext)
  if (context === undefined) {
    throw new Error("useSettings must be used within a SettingsProvider")
  }
  return context
}

// Lightweight hook for components that only need basic settings
export function useCaptureSettings() {
  const { captureInterval, timezone, loading } = useSettings()
  return { captureInterval, timezone, loading }
}
