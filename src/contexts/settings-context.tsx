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
import { toast } from "@/lib/toast"

interface SettingsContextType {
  // Core settings
  captureInterval: number
  timezone: string
  generateThumbnails: boolean
  imageCaptureType: "PNG" | "JPG"

  // API settings
  openWeatherApiKey: string
  apiKeyModified: boolean
  originalApiKeyHash: string

  // Weather settings
  weatherEnabled: boolean
  sunriseSunsetEnabled: boolean
  latitude: number | null
  longitude: number | null

  // Logging settings
  logRetentionDays: number
  maxLogFileSize: number
  enableDebugLogging: boolean
  logLevel: string
  enableLogRotation: boolean
  enableLogCompression: boolean
  maxLogFiles: number

  // Corruption detection settings
  corruptionDetectionEnabled: boolean
  corruptionScoreThreshold: number
  corruptionAutoDiscardEnabled: boolean
  corruptionAutoDisableDegraded: boolean
  corruptionDegradedConsecutiveThreshold: number
  corruptionDegradedTimeWindowMinutes: number
  corruptionDegradedFailurePercentage: number
  corruptionHeavyDetectionEnabled: boolean

  // Loading states
  loading: boolean
  saving: boolean
  error: string | null

  // Actions
  updateSetting: (key: string, value: any) => Promise<boolean>
  updateMultipleSettings: (settings: Record<string, any>) => Promise<boolean>
  getSetting: (key: string) => Promise<string | null>
  deleteSetting: (key: string) => Promise<boolean>
  saveAllSettings: () => Promise<boolean>
  refetch: () => Promise<void>
  
  // Setters for controlled components
  setOpenWeatherApiKey: (value: string) => void
  setApiKeyModified: (value: boolean) => void
  setWeatherEnabled: (value: boolean) => void
  setSunriseSunsetEnabled: (value: boolean) => void
  setLatitude: (value: number | null) => void
  setLongitude: (value: number | null) => void
  setLogRetentionDays: (value: number) => void
  setMaxLogFileSize: (value: number) => void
  setEnableDebugLogging: (value: boolean) => void
  setLogLevel: (value: string) => void
  setEnableLogRotation: (value: boolean) => void
  setEnableLogCompression: (value: boolean) => void
  setMaxLogFiles: (value: number) => void
  setCorruptionDetectionEnabled: (value: boolean) => void
  setCorruptionScoreThreshold: (value: number) => void
  setCorruptionAutoDiscardEnabled: (value: boolean) => void
  setCorruptionAutoDisableDegraded: (value: boolean) => void
  setCorruptionDegradedConsecutiveThreshold: (value: number) => void
  setCorruptionDegradedTimeWindowMinutes: (value: number) => void
  setCorruptionDegradedFailurePercentage: (value: number) => void
  setCorruptionHeavyDetectionEnabled: (value: boolean) => void
}

const SettingsContext = createContext<SettingsContextType | undefined>(
  undefined
)

interface SettingsProviderProps {
  children: ReactNode
}

export function SettingsProvider({ children }: SettingsProviderProps) {
  const [settings, setSettings] = useState({
    // Core settings
    captureInterval: 300,
    timezone: "America/Chicago",
    generateThumbnails: true,
    imageCaptureType: "JPG" as const,
    
    // API settings
    openWeatherApiKey: "",
    apiKeyModified: false,
    originalApiKeyHash: "",
    
    // Weather settings
    weatherEnabled: false,
    sunriseSunsetEnabled: false,
    latitude: null as number | null,
    longitude: null as number | null,
    
    // Logging settings
    logRetentionDays: 30,
    maxLogFileSize: 100,
    enableDebugLogging: false,
    logLevel: "info",
    enableLogRotation: true,
    enableLogCompression: false,
    maxLogFiles: 10,
    
    // Corruption detection settings
    corruptionDetectionEnabled: true,
    corruptionScoreThreshold: 70,
    corruptionAutoDiscardEnabled: false,
    corruptionAutoDisableDegraded: false,
    corruptionDegradedConsecutiveThreshold: 10,
    corruptionDegradedTimeWindowMinutes: 30,
    corruptionDegradedFailurePercentage: 50,
    corruptionHeavyDetectionEnabled: false,
  })

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastFetch, setLastFetch] = useState(0)

  const fetchSettings = useCallback(
    async (force = false) => {
      const now = Date.now()
      // Cache for 5 minutes unless forced
      if (!force && now - lastFetch < 300000 && !loading) return

      try {
        setError(null)
        
        // Fetch core settings
        const response = await fetch("/api/settings")
        if (!response.ok) {
          throw new Error(`Settings fetch failed: ${response.status}`)
        }
        const data = await response.json()

        // Fetch corruption settings
        let corruptionData = {}
        try {
          const corruptionResponse = await fetch("/api/corruption/settings")
          if (corruptionResponse.ok) {
            const corruptionResult = await corruptionResponse.json()
            corruptionData = corruptionResult.global_settings || {}
          }
        } catch (corruptionError) {
          console.warn("Failed to fetch corruption settings:", corruptionError)
        }

        setSettings({
          // Core settings
          captureInterval: parseCaptureInterval(data.capture_interval),
          timezone: data.timezone || "America/Chicago",
          generateThumbnails: data.generate_thumbnails !== false,
          imageCaptureType: data.image_capture_type || "JPG",
          
          // API settings
          openWeatherApiKey: data.openweather_api_key || "",
          apiKeyModified: false, // Reset on fetch
          originalApiKeyHash: data.openweather_api_key || "",
          
          // Weather settings
          weatherEnabled: data.weather_enabled === "true",
          sunriseSunsetEnabled: data.sunrise_sunset_enabled === "true",
          latitude: data.latitude ? parseFloat(data.latitude) : null,
          longitude: data.longitude ? parseFloat(data.longitude) : null,
          
          // Logging settings
          logRetentionDays: parseInt(data.log_retention_days || "30"),
          maxLogFileSize: parseInt(data.max_log_file_size || "100"),
          enableDebugLogging: data.enable_debug_logging === "true",
          logLevel: data.log_level || "info",
          enableLogRotation: data.enable_log_rotation !== "false",
          enableLogCompression: data.enable_log_compression === "true",
          maxLogFiles: parseInt(data.max_log_files || "10"),
          
          // Corruption detection settings
          corruptionDetectionEnabled: (corruptionData as any).corruption_detection_enabled !== false,
          corruptionScoreThreshold: parseInt((corruptionData as any).corruption_score_threshold || "70"),
          corruptionAutoDiscardEnabled: (corruptionData as any).corruption_auto_discard_enabled === true,
          corruptionAutoDisableDegraded: (corruptionData as any).corruption_auto_disable_degraded === true,
          corruptionDegradedConsecutiveThreshold: parseInt((corruptionData as any).corruption_degraded_consecutive_threshold || "10"),
          corruptionDegradedTimeWindowMinutes: parseInt((corruptionData as any).corruption_degraded_time_window_minutes || "30"),
          corruptionDegradedFailurePercentage: parseInt((corruptionData as any).corruption_degraded_failure_percentage || "50"),
          corruptionHeavyDetectionEnabled: false, // Will be set based on camera settings
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
        const response = await fetch(`/api/settings/${encodeURIComponent(key)}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ value: String(value) }),
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

  const updateMultipleSettings = useCallback(
    async (settings: Record<string, any>): Promise<boolean> => {
      try {
        const response = await fetch("/api/settings/bulk", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(settings), // Direct object, frontend proxy will wrap it
        })

        if (!response.ok) {
          throw new Error(`Bulk settings update failed: ${response.status}`)
        }

        // Update local state for all settings
        setSettings((prev) => {
          const updated = { ...prev }
          Object.entries(settings).forEach(([key, value]) => {
            updated[key as keyof typeof prev] =
              key === "captureInterval" ? parseCaptureInterval(value) : value
          })
          return updated
        })

        return true
      } catch (err) {
        console.error("Failed to update multiple settings:", err)
        setError(err instanceof Error ? err.message : "Bulk update failed")
        return false
      }
    },
    []
  )

  const getSetting = useCallback(
    async (key: string): Promise<string | null> => {
      try {
        const response = await fetch(`/api/settings/${encodeURIComponent(key)}`)

        if (response.status === 404) {
          return null // Setting doesn't exist
        }

        if (!response.ok) {
          throw new Error(`Failed to get setting: ${response.status}`)
        }

        const result = await response.json()
        return result.data?.value || null
      } catch (err) {
        console.error("Failed to get setting:", err)
        setError(err instanceof Error ? err.message : "Get setting failed")
        return null
      }
    },
    []
  )

  const deleteSetting = useCallback(
    async (key: string): Promise<boolean> => {
      try {
        const response = await fetch(`/api/settings/${encodeURIComponent(key)}`, {
          method: "DELETE",
        })

        if (!response.ok) {
          throw new Error(`Failed to delete setting: ${response.status}`)
        }

        // Remove from local state if it exists
        setSettings((prev) => {
          const updated = { ...prev }
          if (key in updated) {
            delete updated[key as keyof typeof prev]
          }
          return updated
        })

        return true
      } catch (err) {
        console.error("Failed to delete setting:", err)
        setError(err instanceof Error ? err.message : "Delete setting failed")
        return false
      }
    },
    []
  )

  // Setter functions for controlled components
  const setOpenWeatherApiKey = useCallback((value: string) => {
    setSettings(prev => ({ ...prev, openWeatherApiKey: value, apiKeyModified: true }))
  }, [])

  const setApiKeyModified = useCallback((value: boolean) => {
    setSettings(prev => ({ ...prev, apiKeyModified: value }))
  }, [])

  const setWeatherEnabled = useCallback((value: boolean) => {
    setSettings(prev => ({ ...prev, weatherEnabled: value }))
  }, [])

  const setSunriseSunsetEnabled = useCallback((value: boolean) => {
    setSettings(prev => ({ ...prev, sunriseSunsetEnabled: value }))
  }, [])

  const setLatitude = useCallback((value: number | null) => {
    setSettings(prev => ({ ...prev, latitude: value }))
  }, [])

  const setLongitude = useCallback((value: number | null) => {
    setSettings(prev => ({ ...prev, longitude: value }))
  }, [])

  const setLogRetentionDays = useCallback((value: number) => {
    setSettings(prev => ({ ...prev, logRetentionDays: value }))
  }, [])

  const setMaxLogFileSize = useCallback((value: number) => {
    setSettings(prev => ({ ...prev, maxLogFileSize: value }))
  }, [])

  const setEnableDebugLogging = useCallback((value: boolean) => {
    setSettings(prev => ({ ...prev, enableDebugLogging: value }))
  }, [])

  const setLogLevel = useCallback((value: string) => {
    setSettings(prev => ({ ...prev, logLevel: value }))
  }, [])

  const setEnableLogRotation = useCallback((value: boolean) => {
    setSettings(prev => ({ ...prev, enableLogRotation: value }))
  }, [])

  const setEnableLogCompression = useCallback((value: boolean) => {
    setSettings(prev => ({ ...prev, enableLogCompression: value }))
  }, [])

  const setMaxLogFiles = useCallback((value: number) => {
    setSettings(prev => ({ ...prev, maxLogFiles: value }))
  }, [])

  const setCorruptionDetectionEnabled = useCallback((value: boolean) => {
    setSettings(prev => ({ ...prev, corruptionDetectionEnabled: value }))
  }, [])

  const setCorruptionScoreThreshold = useCallback((value: number) => {
    setSettings(prev => ({ ...prev, corruptionScoreThreshold: value }))
  }, [])

  const setCorruptionAutoDiscardEnabled = useCallback((value: boolean) => {
    setSettings(prev => ({ ...prev, corruptionAutoDiscardEnabled: value }))
  }, [])

  const setCorruptionAutoDisableDegraded = useCallback((value: boolean) => {
    setSettings(prev => ({ ...prev, corruptionAutoDisableDegraded: value }))
  }, [])

  const setCorruptionDegradedConsecutiveThreshold = useCallback((value: number) => {
    setSettings(prev => ({ ...prev, corruptionDegradedConsecutiveThreshold: value }))
  }, [])

  const setCorruptionDegradedTimeWindowMinutes = useCallback((value: number) => {
    setSettings(prev => ({ ...prev, corruptionDegradedTimeWindowMinutes: value }))
  }, [])

  const setCorruptionDegradedFailurePercentage = useCallback((value: number) => {
    setSettings(prev => ({ ...prev, corruptionDegradedFailurePercentage: value }))
  }, [])

  const setCorruptionHeavyDetectionEnabled = useCallback((value: boolean) => {
    setSettings(prev => ({ ...prev, corruptionHeavyDetectionEnabled: value }))
  }, [])

  // Save all settings function (equivalent to the page-specific hook's saveSettings)
  const saveAllSettings = useCallback(async (): Promise<boolean> => {
    setSaving(true)
    try {
      const changedSettings: string[] = []

      // Prepare core settings for bulk update
      const coreSettings = {
        capture_interval: settings.captureInterval.toString(),
        timezone: settings.timezone,
        generate_thumbnails: settings.generateThumbnails.toString(),
        image_capture_type: settings.imageCaptureType,
        log_retention_days: settings.logRetentionDays.toString(),
        max_log_file_size: settings.maxLogFileSize.toString(),
        enable_debug_logging: settings.enableDebugLogging.toString(),
        log_level: settings.logLevel,
        enable_log_rotation: settings.enableLogRotation.toString(),
        enable_log_compression: settings.enableLogCompression.toString(),
        max_log_files: settings.maxLogFiles.toString(),
      }
      

      // Add API key if modified
      if (settings.apiKeyModified && settings.openWeatherApiKey.trim()) {
        coreSettings['openweather_api_key'] = settings.openWeatherApiKey
      }

      // Save core settings in bulk
      const coreSuccess = await updateMultipleSettings(coreSettings)
      if (coreSuccess) {
        changedSettings.push('core_settings')
      }

      // Save weather settings
      const weatherSettings = {
        weather_enabled: settings.weatherEnabled.toString(),
        sunrise_sunset_enabled: settings.sunriseSunsetEnabled.toString(),
        latitude: settings.latitude !== null ? settings.latitude.toString() : "",
        longitude: settings.longitude !== null ? settings.longitude.toString() : "",
      }

      const weatherSuccess = await updateMultipleSettings(weatherSettings)
      if (weatherSuccess) {
        changedSettings.push('weather_settings')
      }

      // Save corruption settings
      const corruptionSettings = {
        global_settings: {
          corruption_detection_enabled: settings.corruptionDetectionEnabled,
          corruption_score_threshold: settings.corruptionScoreThreshold,
          corruption_auto_discard_enabled: settings.corruptionAutoDiscardEnabled,
          corruption_auto_disable_degraded: settings.corruptionAutoDisableDegraded,
          corruption_degraded_consecutive_threshold: settings.corruptionDegradedConsecutiveThreshold,
          corruption_degraded_time_window_minutes: settings.corruptionDegradedTimeWindowMinutes,
          corruption_degraded_failure_percentage: settings.corruptionDegradedFailurePercentage,
        },
        camera_settings: {
          heavy_detection_enabled: settings.corruptionHeavyDetectionEnabled,
        },
      }

      try {
        const corruptionResponse = await fetch("/api/corruption/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(corruptionSettings),
        })

        if (corruptionResponse.ok) {
          changedSettings.push('corruption_settings')
        }
      } catch (corruptionError) {
        console.error("Failed to save corruption settings:", corruptionError)
      }

      // Reset API key modification flag if it was saved
      if (settings.apiKeyModified && settings.openWeatherApiKey.trim()) {
        setApiKeyModified(false)
        setOpenWeatherApiKey("")
      }

      // Show success notification and refresh settings from database
      if (changedSettings.length > 0) {
        toast.success("✅ Settings saved successfully!", {
          description: `Updated: ${changedSettings.join(', ')}`,
          duration: 4000,
        })
        
        // Refresh settings from database to ensure consistency
        await fetchSettings(true)
      }

      return changedSettings.length > 0
    } catch (error) {
      console.error("Failed to save settings:", error)
      setError(error instanceof Error ? error.message : "Save failed")
      
      // Show error notification
      toast.error("❌ Failed to save settings", {
        description: error instanceof Error ? error.message : "Please try again",
        duration: 5000,
      })
      
      return false
    } finally {
      setSaving(false)
    }
  }, [settings, updateMultipleSettings, setApiKeyModified, setOpenWeatherApiKey, fetchSettings])

  useEffect(() => {
    fetchSettings()
  }, [fetchSettings])

  const value: SettingsContextType = {
    ...settings,
    loading,
    saving,
    error,
    updateSetting,
    updateMultipleSettings,
    getSetting,
    deleteSetting,
    saveAllSettings,
    refetch: () => fetchSettings(true),
    
    // Setters
    setOpenWeatherApiKey,
    setApiKeyModified,
    setWeatherEnabled,
    setSunriseSunsetEnabled,
    setLatitude,
    setLongitude,
    setLogRetentionDays,
    setMaxLogFileSize,
    setEnableDebugLogging,
    setLogLevel,
    setEnableLogRotation,
    setEnableLogCompression,
    setMaxLogFiles,
    setCorruptionDetectionEnabled,
    setCorruptionScoreThreshold,
    setCorruptionAutoDiscardEnabled,
    setCorruptionAutoDisableDegraded,
    setCorruptionDegradedConsecutiveThreshold,
    setCorruptionDegradedTimeWindowMinutes,
    setCorruptionDegradedFailurePercentage,
    setCorruptionHeavyDetectionEnabled,
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

// Hook for components that need extended settings functionality
export function useSettingsActions() {
  const { 
    saveAllSettings, 
    updateSetting, 
    updateMultipleSettings, 
    saving, 
    error,
    refetch 
  } = useSettings()
  
  return { 
    saveAllSettings, 
    updateSetting, 
    updateMultipleSettings, 
    saving, 
    error,
    refetch 
  }
}

// Hook for weather-related settings
export function useWeatherSettings() {
  const {
    weatherEnabled,
    sunriseSunsetEnabled,
    latitude,
    longitude,
    openWeatherApiKey,
    apiKeyModified,
    originalApiKeyHash,
    setWeatherEnabled,
    setSunriseSunsetEnabled,
    setLatitude,
    setLongitude,
    setOpenWeatherApiKey,
    setApiKeyModified,
  } = useSettings()
  
  return {
    weatherEnabled,
    sunriseSunsetEnabled,
    latitude,
    longitude,
    openWeatherApiKey,
    apiKeyModified,
    originalApiKeyHash,
    setWeatherEnabled,
    setSunriseSunsetEnabled,
    setLatitude,
    setLongitude,
    setOpenWeatherApiKey,
    setApiKeyModified,
  }
}
