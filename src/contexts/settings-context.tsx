"use client"

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useMemo,
  ReactNode,
} from "react"
import { toast } from "@/lib/toast"

interface SettingsContextType {
  // Core settings
  timezone: string
  enableThumbnailGeneration: boolean
  smallGenerationMode: "all" | "latest" | "disabled"
  purgeSmalllsOnCompletion: boolean
  imageCaptureType: "PNG" | "JPG"

  // API settings
  openWeatherApiKey: string
  apiKeyModified: boolean
  originalApiKeyHash: string

  // Weather settings
  weatherIntegrationEnabled: boolean
  weatherRecordData: boolean
  sunriseSunsetEnabled: boolean
  temperatureUnit: "celsius" | "fahrenheit"
  latitude: number | null
  longitude: number | null

  // Weather data (cached from hourly updates)
  weatherDateFetched: string | null
  currentTemp: number | null
  currentWeatherIcon: string | null
  currentWeatherDescription: string | null
  sunriseTimestamp: string | null
  sunsetTimestamp: string | null

  // Database logging settings (for application events in PostgreSQL)
  dbLogRetentionDays: number
  dbLogLevel: string

  // File logging settings (for system debugging with loguru)
  fileLogRetentionDays: number
  maxLogFileSize: number
  fileLogLevel: string
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

  // Thumbnail job settings
  thumbnailJobBatchSize: number
  thumbnailWorkerInterval: number
  thumbnailMaxRetries: number
  thumbnailHighLoadMode: boolean
  thumbnailConcurrentJobs: number
  thumbnailMemoryLimit: number

  // Loading states
  loading: boolean
  saving: boolean
  error: string | null
  hasUnsavedChanges: boolean

  // Actions
  updateSetting: (key: string, value: any) => Promise<boolean>
  updateMultipleSettings: (settings: Record<string, any>) => Promise<boolean>
  getSetting: (key: string) => Promise<string | null>
  deleteSetting: (key: string) => Promise<boolean>
  saveAllSettings: () => Promise<boolean>
  refetch: () => Promise<void>

  // Setters for controlled components
  setTimezone: (value: string) => void
  setEnableThumbnailGeneration: (value: boolean) => Promise<void>
  setSmallGenerationMode: (
    value: "all" | "latest" | "disabled"
  ) => Promise<void>
  setPurgeSmalllsOnCompletion: (value: boolean) => Promise<void>
  setImageCaptureType: (value: "PNG" | "JPG") => void
  setOpenWeatherApiKey: (value: string) => void
  setApiKeyModified: (value: boolean) => void
  setWeatherIntegrationEnabled: (value: boolean) => void
  setWeatherRecordData: (value: boolean) => void
  setSunriseSunsetEnabled: (value: boolean) => void
  setTemperatureUnit: (value: "celsius" | "fahrenheit") => void
  setLatitude: (value: number | null) => void
  setLongitude: (value: number | null) => void
  setDbLogRetentionDays: (value: number) => void
  setDbLogLevel: (value: string) => void
  setFileLogRetentionDays: (value: number) => void
  setMaxLogFileSize: (value: number) => void
  setFileLogLevel: (value: string) => void
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
  setThumbnailJobBatchSize: (value: number) => void
  setThumbnailWorkerInterval: (value: number) => void
  setThumbnailMaxRetries: (value: number) => void
  setThumbnailHighLoadMode: (value: boolean) => void
  setThumbnailConcurrentJobs: (value: number) => void
  setThumbnailMemoryLimit: (value: number) => void
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
    timezone: "America/Chicago",
    enableThumbnailGeneration: true,
    smallGenerationMode: "disabled" as "all" | "latest" | "disabled",
    purgeSmalllsOnCompletion: false,
    imageCaptureType: "JPG" as "PNG" | "JPG",

    // API settings
    openWeatherApiKey: "",
    apiKeyModified: false,
    originalApiKeyHash: "",

    // Weather settings
    weatherIntegrationEnabled: false,
    weatherRecordData: false,
    sunriseSunsetEnabled: false,
    temperatureUnit: "celsius" as "celsius" | "fahrenheit",
    latitude: null as number | null,
    longitude: null as number | null,

    // Weather data (cached from hourly updates)
    weatherDateFetched: null as string | null,
    currentTemp: null as number | null,
    currentWeatherIcon: null as string | null,
    currentWeatherDescription: null as string | null,
    sunriseTimestamp: null as string | null,
    sunsetTimestamp: null as string | null,

    // Database logging settings (for application events in PostgreSQL)
    dbLogRetentionDays: 30,
    dbLogLevel: "info",

    // File logging settings (for system debugging with loguru)
    fileLogRetentionDays: 7,
    maxLogFileSize: 100,
    fileLogLevel: "info",
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

    // Thumbnail job settings
    thumbnailJobBatchSize: 10,
    thumbnailWorkerInterval: 3,
    thumbnailMaxRetries: 3,
    thumbnailHighLoadMode: false,
    thumbnailConcurrentJobs: 3,
    thumbnailMemoryLimit: 512,
  })

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastFetch, setLastFetch] = useState(0)
  const [originalSettings, setOriginalSettings] = useState<
    typeof settings | null
  >(null)

  const fetchSettings = useCallback(
    async (force = false) => {
      const now = Date.now()
      // DISABLED: Cache for 5 minutes unless forced
      // if (!force && now - lastFetch < 300000 && !loading) return

      try {
        setError(null)

        // Fetch core settings with no-cache headers
        const response = await fetch("/api/settings", {
          cache: "no-store",
          headers: {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            Pragma: "no-cache",
            Expires: "0",
          },
        })
        if (!response.ok) {
          throw new Error(`Settings fetch failed: ${response.status}`)
        }
        const data = await response.json()
        console.log("🔍 Settings fetched from backend:", {
          image_capture_type: data.data.image_capture_type,
          capture_interval: data.data.capture_interval,
          timezone: data.data.timezone,
        })

        // Fetch corruption settings
        let corruptionData = {}
        try {
          const corruptionResponse = await fetch("/api/settings/corruption", {
            cache: "no-store",
            headers: {
              "Cache-Control": "no-cache, no-store, must-revalidate",
              Pragma: "no-cache",
              Expires: "0",
            },
          })
          if (corruptionResponse.ok) {
            const corruptionResult = await corruptionResponse.json()
            corruptionData = corruptionResult.global_settings || {}
          }
        } catch (corruptionError) {
          console.warn("Failed to fetch corruption settings:", corruptionError)
        }

        const newSettings = {
          // Core settings
          timezone: data.data.timezone || "America/Chicago",
          enableThumbnailGeneration: data.data.generate_thumbnails === "true",
          smallGenerationMode: (data.data.thumbnail_small_generation_mode ===
          "all"
            ? "all"
            : data.data.thumbnail_small_generation_mode === "latest"
            ? "latest"
            : "disabled") as "all" | "latest" | "disabled",
          purgeSmalllsOnCompletion:
            data.data.thumbnail_purge_smalls_on_completion === "true",
          imageCaptureType: (data.data.image_capture_type || "JPG") as
            | "PNG"
            | "JPG",

          // API settings - the backend now returns the actual key for display
          openWeatherApiKey: data.data.openweather_api_key || "", // Store actual key for display
          apiKeyModified: false, // Reset on fetch
          originalApiKeyHash:
            data.data.openweather_api_key_hash ||
            (data.data.openweather_api_key ? "stored" : ""),

          // Weather settings (with fallbacks for backend compatibility)
          weatherIntegrationEnabled:
            data.data.weather_integration_enabled === "true" ||
            data.data.weather_enabled === "true",
          weatherRecordData: data.data.weather_enabled === "true",
          sunriseSunsetEnabled: data.data.sunrise_sunset_enabled === "true",
          temperatureUnit: (data.data.temperature_unit === "fahrenheit"
            ? "fahrenheit"
            : "celsius") as "celsius" | "fahrenheit",
          latitude: data.data.latitude ? parseFloat(data.data.latitude) : null,
          longitude: data.data.longitude
            ? parseFloat(data.data.longitude)
            : null,

          // Weather data (cached from hourly updates)
          weatherDateFetched: data.data.weather_date_fetched || null,
          currentTemp: data.data.current_temp
            ? parseFloat(data.data.current_temp)
            : null,
          currentWeatherIcon: data.data.current_weather_icon || null,
          currentWeatherDescription:
            data.data.current_weather_description || null,
          sunriseTimestamp: data.data.sunrise_timestamp || null,
          sunsetTimestamp: data.data.sunset_timestamp || null,

          // Logging settings
          dbLogRetentionDays: parseInt(data.data.log_retention_days || "30"),
          dbLogLevel: data.data.log_level || "info",
          fileLogRetentionDays: parseInt(
            data.data.file_log_retention_days || "7"
          ),
          maxLogFileSize: parseInt(data.data.max_log_file_size || "100"),
          fileLogLevel: data.data.file_log_level || "info",
          enableLogRotation: data.data.enable_log_rotation !== "false",
          enableLogCompression: data.data.enable_log_compression === "true",
          maxLogFiles: parseInt(data.data.max_log_files || "10"),

          // Corruption detection settings
          corruptionDetectionEnabled:
            (corruptionData as any).corruption_detection_enabled !== false,
          corruptionScoreThreshold: parseInt(
            (corruptionData as any).corruption_score_threshold || "70"
          ),
          corruptionAutoDiscardEnabled:
            (corruptionData as any).corruption_auto_discard_enabled === true,
          corruptionAutoDisableDegraded:
            (corruptionData as any).corruption_auto_disable_degraded === true,
          corruptionDegradedConsecutiveThreshold: parseInt(
            (corruptionData as any).corruption_degraded_consecutive_threshold ||
              "10"
          ),
          corruptionDegradedTimeWindowMinutes: parseInt(
            (corruptionData as any).corruption_degraded_time_window_minutes ||
              "30"
          ),
          corruptionDegradedFailurePercentage: parseInt(
            (corruptionData as any).corruption_degraded_failure_percentage ||
              "50"
          ),
          corruptionHeavyDetectionEnabled: false, // Will be set based on camera settings

          // Thumbnail job settings
          thumbnailJobBatchSize: parseInt(
            data.data.thumbnail_job_batch_size || "10"
          ),
          thumbnailWorkerInterval: parseInt(
            data.data.thumbnail_worker_interval || "3"
          ),
          thumbnailMaxRetries: parseInt(data.data.thumbnail_max_retries || "3"),
          thumbnailHighLoadMode: data.data.thumbnail_high_load_mode === "true",
          thumbnailConcurrentJobs: parseInt(
            data.data.thumbnail_concurrent_jobs || "3"
          ),
          thumbnailMemoryLimit: parseInt(
            data.data.thumbnail_memory_limit_mb || "512"
          ),
        }

        setSettings(newSettings)
        setOriginalSettings(newSettings) // Store original for change detection

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
        const response = await fetch(
          `/api/settings/${encodeURIComponent(key)}`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ value: String(value) }),
          }
        )

        if (!response.ok) {
          throw new Error(`Settings update failed: ${response.status}`)
        }

        // Update local state
        setSettings((prev) => ({
          ...prev,
          [key]: value,
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

        // Wait for the response to complete before returning
        const result = await response.json()

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

  const deleteSetting = useCallback(async (key: string): Promise<boolean> => {
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
  }, [])

  // Setter functions for controlled components
  const setTimezone = useCallback((value: string) => {
    setSettings((prev) => ({ ...prev, timezone: value }))
  }, [])

  const setEnableThumbnailGeneration = useCallback(
    async (value: boolean) => {
      setSettings((prev) => ({ ...prev, enableThumbnailGeneration: value }))
      // Auto-save immediately
      try {
        await updateSetting("enable_thumbnail_generation", value)
        // Update original settings to reflect saved state
        setOriginalSettings((prev) =>
          prev ? { ...prev, enableThumbnailGeneration: value } : null
        )
        toast.success("Thumbnail generation setting saved")
      } catch (error) {
        console.error("Failed to save thumbnail generation setting:", error)
        toast.error("Failed to save setting")
      }
    },
    [updateSetting]
  )

  const setSmallGenerationMode = useCallback(
    async (value: "all" | "latest" | "disabled") => {
      setSettings((prev) => ({ ...prev, smallGenerationMode: value }))
      // Auto-save immediately
      try {
        await updateSetting("small_generation_mode", value)
        // Update original settings to reflect saved state
        setOriginalSettings((prev) =>
          prev ? { ...prev, smallGenerationMode: value } : null
        )
        toast.success("Small image mode setting saved")
      } catch (error) {
        console.error("Failed to save small generation mode:", error)
        toast.error("Failed to save setting")
      }
    },
    [updateSetting]
  )

  const setPurgeSmalllsOnCompletion = useCallback(
    async (value: boolean) => {
      setSettings((prev) => ({ ...prev, purgeSmalllsOnCompletion: value }))
      // Auto-save immediately
      try {
        await updateSetting("purge_smalls_on_completion", value)
        // Update original settings to reflect saved state
        setOriginalSettings((prev) =>
          prev ? { ...prev, purgeSmalllsOnCompletion: value } : null
        )
        toast.success("Auto-purge setting saved")
      } catch (error) {
        console.error("Failed to save auto-purge setting:", error)
        toast.error("Failed to save setting")
      }
    },
    [updateSetting]
  )

  const setImageCaptureType = useCallback((value: "PNG" | "JPG") => {
    setSettings((prev) => ({ ...prev, imageCaptureType: value }))
  }, [])

  const setOpenWeatherApiKey = useCallback((value: string) => {
    setSettings((prev) => ({
      ...prev,
      openWeatherApiKey: value,
      apiKeyModified: true,
    }))
  }, [])

  const setApiKeyModified = useCallback((value: boolean) => {
    setSettings((prev) => ({ ...prev, apiKeyModified: value }))
  }, [])

  const setWeatherIntegrationEnabled = useCallback((value: boolean) => {
    setSettings((prev) => ({ ...prev, weatherIntegrationEnabled: value }))
  }, [])

  const setWeatherRecordData = useCallback((value: boolean) => {
    setSettings((prev) => ({ ...prev, weatherRecordData: value }))
  }, [])

  const setSunriseSunsetEnabled = useCallback((value: boolean) => {
    setSettings((prev) => ({ ...prev, sunriseSunsetEnabled: value }))
  }, [])

  const setTemperatureUnit = useCallback((value: "celsius" | "fahrenheit") => {
    setSettings((prev) => ({ ...prev, temperatureUnit: value }))
  }, [])

  const setLatitude = useCallback((value: number | null) => {
    setSettings((prev) => ({ ...prev, latitude: value }))
  }, [])

  const setLongitude = useCallback((value: number | null) => {
    setSettings((prev) => ({ ...prev, longitude: value }))
  }, [])

  const setDbLogRetentionDays = useCallback((value: number) => {
    setSettings((prev) => ({ ...prev, dbLogRetentionDays: value }))
  }, [])

  const setDbLogLevel = useCallback((value: string) => {
    setSettings((prev) => ({ ...prev, dbLogLevel: value }))
  }, [])

  const setFileLogRetentionDays = useCallback((value: number) => {
    setSettings((prev) => ({ ...prev, fileLogRetentionDays: value }))
  }, [])

  const setMaxLogFileSize = useCallback((value: number) => {
    setSettings((prev) => ({ ...prev, maxLogFileSize: value }))
  }, [])

  const setFileLogLevel = useCallback((value: string) => {
    setSettings((prev) => ({ ...prev, fileLogLevel: value }))
  }, [])

  const setEnableLogRotation = useCallback((value: boolean) => {
    setSettings((prev) => ({ ...prev, enableLogRotation: value }))
  }, [])

  const setEnableLogCompression = useCallback((value: boolean) => {
    setSettings((prev) => ({ ...prev, enableLogCompression: value }))
  }, [])

  const setMaxLogFiles = useCallback((value: number) => {
    setSettings((prev) => ({ ...prev, maxLogFiles: value }))
  }, [])

  const setCorruptionDetectionEnabled = useCallback((value: boolean) => {
    setSettings((prev) => ({ ...prev, corruptionDetectionEnabled: value }))
  }, [])

  const setCorruptionScoreThreshold = useCallback((value: number) => {
    setSettings((prev) => ({ ...prev, corruptionScoreThreshold: value }))
  }, [])

  const setCorruptionAutoDiscardEnabled = useCallback((value: boolean) => {
    setSettings((prev) => ({ ...prev, corruptionAutoDiscardEnabled: value }))
  }, [])

  const setCorruptionAutoDisableDegraded = useCallback((value: boolean) => {
    setSettings((prev) => ({ ...prev, corruptionAutoDisableDegraded: value }))
  }, [])

  const setCorruptionDegradedConsecutiveThreshold = useCallback(
    (value: number) => {
      setSettings((prev) => ({
        ...prev,
        corruptionDegradedConsecutiveThreshold: value,
      }))
    },
    []
  )

  const setCorruptionDegradedTimeWindowMinutes = useCallback(
    (value: number) => {
      setSettings((prev) => ({
        ...prev,
        corruptionDegradedTimeWindowMinutes: value,
      }))
    },
    []
  )

  const setCorruptionDegradedFailurePercentage = useCallback(
    (value: number) => {
      setSettings((prev) => ({
        ...prev,
        corruptionDegradedFailurePercentage: value,
      }))
    },
    []
  )

  const setCorruptionHeavyDetectionEnabled = useCallback((value: boolean) => {
    setSettings((prev) => ({ ...prev, corruptionHeavyDetectionEnabled: value }))
  }, [])

  // Thumbnail job setter functions
  const setThumbnailJobBatchSize = useCallback((value: number) => {
    setSettings((prev) => ({ ...prev, thumbnailJobBatchSize: value }))
  }, [])

  const setThumbnailWorkerInterval = useCallback((value: number) => {
    setSettings((prev) => ({ ...prev, thumbnailWorkerInterval: value }))
  }, [])

  const setThumbnailMaxRetries = useCallback((value: number) => {
    setSettings((prev) => ({ ...prev, thumbnailMaxRetries: value }))
  }, [])

  const setThumbnailHighLoadMode = useCallback((value: boolean) => {
    setSettings((prev) => ({ ...prev, thumbnailHighLoadMode: value }))
  }, [])

  const setThumbnailConcurrentJobs = useCallback((value: number) => {
    setSettings((prev) => ({ ...prev, thumbnailConcurrentJobs: value }))
  }, [])

  const setThumbnailMemoryLimit = useCallback((value: number) => {
    setSettings((prev) => ({ ...prev, thumbnailMemoryLimit: value }))
  }, [])

  // Helper function to detect changed settings
  const detectChangedSettings = useCallback(() => {
    if (!originalSettings) return []

    const changes: string[] = []

    // Core settings
    if (settings.timezone !== originalSettings.timezone) {
      changes.push(`Timezone (${settings.timezone})`)
    }
    if (
      settings.enableThumbnailGeneration !==
      originalSettings.enableThumbnailGeneration
    ) {
      changes.push(
        `Thumbnails (${
          settings.enableThumbnailGeneration ? "enabled" : "disabled"
        })`
      )
    }
    if (settings.smallGenerationMode !== originalSettings.smallGenerationMode) {
      changes.push(`Small Images (${settings.smallGenerationMode})`)
    }
    if (
      settings.purgeSmalllsOnCompletion !==
      originalSettings.purgeSmalllsOnCompletion
    ) {
      changes.push(
        `Auto-purge (${
          settings.purgeSmalllsOnCompletion ? "enabled" : "disabled"
        })`
      )
    }
    if (settings.imageCaptureType !== originalSettings.imageCaptureType) {
      changes.push(`Image Type (${settings.imageCaptureType})`)
    }

    // API Key
    if (settings.apiKeyModified && settings.openWeatherApiKey.trim()) {
      changes.push("OpenWeather API Key")
    }

    // Weather settings
    if (
      settings.weatherIntegrationEnabled !==
      originalSettings.weatherIntegrationEnabled
    ) {
      changes.push(
        `Weather Integration (${
          settings.weatherIntegrationEnabled ? "enabled" : "disabled"
        })`
      )
    }
    if (settings.weatherRecordData !== originalSettings.weatherRecordData) {
      changes.push(
        `Weather Data Recording (${
          settings.weatherRecordData ? "enabled" : "disabled"
        })`
      )
    }
    if (
      settings.sunriseSunsetEnabled !== originalSettings.sunriseSunsetEnabled
    ) {
      changes.push(
        `Sunrise/Sunset (${
          settings.sunriseSunsetEnabled ? "enabled" : "disabled"
        })`
      )
    }
    if (settings.temperatureUnit !== originalSettings.temperatureUnit) {
      changes.push(`Temperature Unit (${settings.temperatureUnit})`)
    }

    // Location
    if (settings.latitude !== originalSettings.latitude) {
      changes.push(`Latitude (${settings.latitude})`)
    }
    if (settings.longitude !== originalSettings.longitude) {
      changes.push(`Longitude (${settings.longitude})`)
    }

    // Logging settings
    if (settings.dbLogRetentionDays !== originalSettings.dbLogRetentionDays) {
      changes.push(`DB Log Retention (${settings.dbLogRetentionDays} days)`)
    }
    if (settings.maxLogFileSize !== originalSettings.maxLogFileSize) {
      changes.push(`Max Log Size (${settings.maxLogFileSize}MB)`)
    }
    if (settings.dbLogLevel !== originalSettings.dbLogLevel) {
      changes.push(`DB Log Level (${settings.dbLogLevel})`)
    }
    if (
      settings.corruptionAutoDiscardEnabled !==
      originalSettings.corruptionAutoDiscardEnabled
    ) {
      changes.push(
        `Auto Discard (${
          settings.corruptionAutoDiscardEnabled ? "enabled" : "disabled"
        })`
      )
    }
    if (settings.fileLogLevel !== originalSettings.fileLogLevel) {
      changes.push(`File Log Level (${settings.fileLogLevel})`)
    }

    // Corruption settings
    if (
      settings.corruptionAutoDisableDegraded !==
      originalSettings.corruptionAutoDisableDegraded
    ) {
      changes.push(
        `Auto Disable Degraded (${
          settings.corruptionAutoDisableDegraded ? "enabled" : "disabled"
        })`
      )
    }
    if (
      settings.corruptionDetectionEnabled !==
      originalSettings.corruptionDetectionEnabled
    ) {
      changes.push(
        `Corruption Detection (${
          settings.corruptionDetectionEnabled ? "enabled" : "disabled"
        })`
      )
    }
    if (
      settings.corruptionScoreThreshold !==
      originalSettings.corruptionScoreThreshold
    ) {
      changes.push(`Score Threshold (${settings.corruptionScoreThreshold})`)
    }
    if (
      settings.corruptionDegradedConsecutiveThreshold !==
      originalSettings.corruptionDegradedConsecutiveThreshold
    ) {
      changes.push(
        `Consecutive Threshold (${settings.corruptionDegradedConsecutiveThreshold})`
      )
    }
    if (
      settings.corruptionDegradedTimeWindowMinutes !==
      originalSettings.corruptionDegradedTimeWindowMinutes
    ) {
      changes.push(
        `Time Window (${settings.corruptionDegradedTimeWindowMinutes} min)`
      )
    }
    if (
      settings.corruptionDegradedFailurePercentage !==
      originalSettings.corruptionDegradedFailurePercentage
    ) {
      changes.push(
        `Failure Percentage (${settings.corruptionDegradedFailurePercentage}%)`
      )
    }
    if (
      settings.corruptionHeavyDetectionEnabled !==
      originalSettings.corruptionHeavyDetectionEnabled
    ) {
      changes.push(
        `Heavy Detection (${
          settings.corruptionHeavyDetectionEnabled ? "enabled" : "disabled"
        })`
      )
    }

    // Thumbnail settings
    if (
      settings.thumbnailMemoryLimit !== originalSettings.thumbnailMemoryLimit
    ) {
      changes.push(
        `Thumbnail Memory Limit (${settings.thumbnailMemoryLimit}MB)`
      )
    }

    return changes
  }, [settings, originalSettings])

  // Computed property for unsaved changes
  const hasUnsavedChanges = useMemo(() => {
    return detectChangedSettings().length > 0
  }, [detectChangedSettings])

  // Save all settings function (equivalent to the page-specific hook's saveSettings)
  const saveAllSettings = useCallback(async (): Promise<boolean> => {
    setSaving(true)
    try {
      // Helper function to detect changed settings
      const detectChangedSettings = () => {
        if (!originalSettings) return []

        const changes: string[] = []

        // Core settings
        if (settings.timezone !== originalSettings.timezone) {
          changes.push(`Timezone (${settings.timezone})`)
        }
        if (
          settings.enableThumbnailGeneration !==
          originalSettings.enableThumbnailGeneration
        ) {
          changes.push(
            `Thumbnails (${
              settings.enableThumbnailGeneration ? "enabled" : "disabled"
            })`
          )
        }
        if (
          settings.smallGenerationMode !== originalSettings.smallGenerationMode
        ) {
          changes.push(`Small Images (${settings.smallGenerationMode})`)
        }
        if (
          settings.purgeSmalllsOnCompletion !==
          originalSettings.purgeSmalllsOnCompletion
        ) {
          changes.push(
            `Auto-purge (${
              settings.purgeSmalllsOnCompletion ? "enabled" : "disabled"
            })`
          )
        }
        if (settings.imageCaptureType !== originalSettings.imageCaptureType) {
          changes.push(`Image Type (${settings.imageCaptureType})`)
        }

        // API Key
        if (settings.apiKeyModified && settings.openWeatherApiKey.trim()) {
          changes.push("OpenWeather API Key")
        }

        // Weather settings
        if (
          settings.weatherIntegrationEnabled !==
          originalSettings.weatherIntegrationEnabled
        ) {
          changes.push(
            `Weather Integration (${
              settings.weatherIntegrationEnabled ? "enabled" : "disabled"
            })`
          )
        }
        if (settings.weatherRecordData !== originalSettings.weatherRecordData) {
          changes.push(
            `Weather Data Collection (${
              settings.weatherRecordData ? "enabled" : "disabled"
            })`
          )
        }
        if (
          settings.sunriseSunsetEnabled !==
          originalSettings.sunriseSunsetEnabled
        ) {
          changes.push(
            `Sunrise/Sunset (${
              settings.sunriseSunsetEnabled ? "enabled" : "disabled"
            })`
          )
        }
        if (settings.temperatureUnit !== originalSettings.temperatureUnit) {
          changes.push(
            `Temperature Unit (${
              settings.temperatureUnit === "fahrenheit"
                ? "Fahrenheit"
                : "Celsius"
            })`
          )
        }
        if (settings.latitude !== originalSettings.latitude) {
          changes.push(`Latitude (${settings.latitude})`)
        }
        if (settings.longitude !== originalSettings.longitude) {
          changes.push(`Longitude (${settings.longitude})`)
        }

        // Logging settings
        if (
          settings.dbLogRetentionDays !== originalSettings.dbLogRetentionDays
        ) {
          changes.push(`DB Log Retention (${settings.dbLogRetentionDays} days)`)
        }
        if (settings.maxLogFileSize !== originalSettings.maxLogFileSize) {
          changes.push(`Max Log Size (${settings.maxLogFileSize}MB)`)
        }
        if (settings.dbLogLevel !== originalSettings.dbLogLevel) {
          changes.push(`DB Log Level (${settings.dbLogLevel})`)
        }
        if (
          settings.fileLogRetentionDays !==
          originalSettings.fileLogRetentionDays
        ) {
          changes.push(
            `File Log Retention (${settings.fileLogRetentionDays} days)`
          )
        }
        if (settings.fileLogLevel !== originalSettings.fileLogLevel) {
          changes.push(`File Log Level (${settings.fileLogLevel})`)
        }

        // Corruption settings
        if (
          settings.corruptionDetectionEnabled !==
          originalSettings.corruptionDetectionEnabled
        ) {
          changes.push(
            `Corruption Detection (${
              settings.corruptionDetectionEnabled ? "enabled" : "disabled"
            })`
          )
        }
        if (
          settings.corruptionScoreThreshold !==
          originalSettings.corruptionScoreThreshold
        ) {
          changes.push(
            `Corruption Threshold (${settings.corruptionScoreThreshold})`
          )
        }
        if (
          settings.corruptionAutoDiscardEnabled !==
          originalSettings.corruptionAutoDiscardEnabled
        ) {
          changes.push(
            `Auto Discard (${
              settings.corruptionAutoDiscardEnabled ? "enabled" : "disabled"
            })`
          )
        }
        if (
          settings.corruptionAutoDisableDegraded !==
          originalSettings.corruptionAutoDisableDegraded
        ) {
          changes.push(
            `Auto Disable Degraded (${
              settings.corruptionAutoDisableDegraded ? "enabled" : "disabled"
            })`
          )
        }
        if (
          settings.corruptionDegradedConsecutiveThreshold !==
          originalSettings.corruptionDegradedConsecutiveThreshold
        ) {
          changes.push(
            `Consecutive Threshold (${settings.corruptionDegradedConsecutiveThreshold})`
          )
        }
        if (
          settings.corruptionDegradedTimeWindowMinutes !==
          originalSettings.corruptionDegradedTimeWindowMinutes
        ) {
          changes.push(
            `Time Window (${settings.corruptionDegradedTimeWindowMinutes} min)`
          )
        }
        if (
          settings.corruptionDegradedFailurePercentage !==
          originalSettings.corruptionDegradedFailurePercentage
        ) {
          changes.push(
            `Failure Percentage (${settings.corruptionDegradedFailurePercentage}%)`
          )
        }
        if (
          settings.corruptionHeavyDetectionEnabled !==
          originalSettings.corruptionHeavyDetectionEnabled
        ) {
          changes.push(
            `Heavy Detection (${
              settings.corruptionHeavyDetectionEnabled ? "enabled" : "disabled"
            })`
          )
        }

        return changes
      }

      const changedFields = detectChangedSettings()
      if (changedFields.length === 0) {
        toast.info("No changes to save", {
          description: "All settings are already up to date",
          duration: 3000,
        })
        setSaving(false)
        return false
      }

      const changedSettings: string[] = []

      // Prepare core settings for bulk update (including corruption settings)
      console.log(
        "📤 Saving settings with imageCaptureType:",
        settings.imageCaptureType
      )
      const coreSettings: Record<string, string> = {
        timezone: settings.timezone,
        generate_thumbnails: settings.enableThumbnailGeneration.toString(),
        thumbnail_small_generation_mode:
          settings.smallGenerationMode.toString(),
        thumbnail_purge_smalls_on_completion:
          settings.purgeSmalllsOnCompletion.toString(),
        image_capture_type: settings.imageCaptureType,
        log_retention_days: settings.dbLogRetentionDays.toString(),
        max_log_file_size: settings.maxLogFileSize.toString(),
        log_level: settings.dbLogLevel,
        file_log_retention_days: settings.fileLogRetentionDays.toString(),
        file_log_level: settings.fileLogLevel,
        enable_log_rotation: settings.enableLogRotation.toString(),
        enable_log_compression: settings.enableLogCompression.toString(),
        max_log_files: settings.maxLogFiles.toString(),

        // Corruption settings (flattened)
        corruption_detection_enabled:
          settings.corruptionDetectionEnabled.toString(),
        corruption_score_threshold:
          settings.corruptionScoreThreshold.toString(),
        corruption_auto_discard_enabled:
          settings.corruptionAutoDiscardEnabled.toString(),
        corruption_auto_disable_degraded:
          settings.corruptionAutoDisableDegraded.toString(),
        corruption_degraded_consecutive_threshold:
          settings.corruptionDegradedConsecutiveThreshold.toString(),
        corruption_degraded_time_window_minutes:
          settings.corruptionDegradedTimeWindowMinutes.toString(),
        corruption_degraded_failure_percentage:
          settings.corruptionDegradedFailurePercentage.toString(),
        corruption_heavy_detection_enabled:
          settings.corruptionHeavyDetectionEnabled.toString(),
      }

      // Add API key if modified
      if (settings.apiKeyModified && settings.openWeatherApiKey.trim()) {
        coreSettings.openweather_api_key = settings.openWeatherApiKey
      }

      // Save core settings in bulk (now includes corruption settings)
      const coreSuccess = await updateMultipleSettings(coreSettings)
      if (coreSuccess) {
        changedSettings.push("core_settings")
      }

      // Save weather settings
      const weatherSettings: Record<string, string> = {
        weather_enabled: settings.weatherRecordData.toString(),
        sunrise_sunset_enabled: settings.sunriseSunsetEnabled.toString(),
        temperature_unit: settings.temperatureUnit,
        latitude:
          settings.latitude !== null ? settings.latitude.toString() : "",
        longitude:
          settings.longitude !== null ? settings.longitude.toString() : "",
      }

      // Add weather_integration_enabled if we have the new field structure
      if (settings.weatherIntegrationEnabled !== settings.weatherRecordData) {
        weatherSettings.weather_integration_enabled =
          settings.weatherIntegrationEnabled.toString()
      }

      const weatherSuccess = await updateMultipleSettings(weatherSettings)
      if (weatherSuccess) {
        changedSettings.push("weather_settings")
      }

      // Reset API key modification flag if it was saved
      if (settings.apiKeyModified && settings.openWeatherApiKey.trim()) {
        setApiKeyModified(false)
        // Keep the API key in state for display purposes
      }

      // Show success notification with actual changed fields
      if (changedSettings.length > 0) {
        toast.success("✅ Settings saved successfully!", {
          description:
            changedFields.length > 3
              ? `Updated ${changedFields.length} settings`
              : `Updated: ${changedFields.join(", ")}`,
          duration: 4000,
        })

        // Update original settings to current for next change detection
        // Need to create a new object with the current values
        const updatedSettings = {
          timezone: settings.timezone,
          enableThumbnailGeneration: settings.enableThumbnailGeneration,
          smallGenerationMode: settings.smallGenerationMode,
          purgeSmalllsOnCompletion: settings.purgeSmalllsOnCompletion,
          imageCaptureType: settings.imageCaptureType,
          openWeatherApiKey: settings.openWeatherApiKey,
          apiKeyModified: false, // Reset after save
          originalApiKeyHash:
            settings.openWeatherApiKey || settings.originalApiKeyHash,
          weatherIntegrationEnabled: settings.weatherIntegrationEnabled,
          weatherRecordData: settings.weatherRecordData,
          sunriseSunsetEnabled: settings.sunriseSunsetEnabled,
          temperatureUnit: settings.temperatureUnit,
          latitude: settings.latitude,
          longitude: settings.longitude,

          // Weather data (cached from hourly updates)
          weatherDateFetched: settings.weatherDateFetched,
          currentTemp: settings.currentTemp,
          currentWeatherIcon: settings.currentWeatherIcon,
          currentWeatherDescription: settings.currentWeatherDescription,
          sunriseTimestamp: settings.sunriseTimestamp,
          sunsetTimestamp: settings.sunsetTimestamp,

          // Database logging settings
          dbLogRetentionDays: settings.dbLogRetentionDays,
          dbLogLevel: settings.dbLogLevel,

          // File logging settings
          fileLogRetentionDays: settings.fileLogRetentionDays,
          maxLogFileSize: settings.maxLogFileSize,
          fileLogLevel: settings.fileLogLevel,
          enableLogRotation: settings.enableLogRotation,
          enableLogCompression: settings.enableLogCompression,
          maxLogFiles: settings.maxLogFiles,

          // Corruption detection settings
          corruptionDetectionEnabled: settings.corruptionDetectionEnabled,
          corruptionScoreThreshold: settings.corruptionScoreThreshold,
          corruptionAutoDiscardEnabled: settings.corruptionAutoDiscardEnabled,
          corruptionAutoDisableDegraded: settings.corruptionAutoDisableDegraded,
          corruptionDegradedConsecutiveThreshold:
            settings.corruptionDegradedConsecutiveThreshold,
          corruptionDegradedTimeWindowMinutes:
            settings.corruptionDegradedTimeWindowMinutes,
          corruptionDegradedFailurePercentage:
            settings.corruptionDegradedFailurePercentage,
          corruptionHeavyDetectionEnabled:
            settings.corruptionHeavyDetectionEnabled,

          // Thumbnail job settings
          thumbnailJobBatchSize: settings.thumbnailJobBatchSize,
          thumbnailWorkerInterval: settings.thumbnailWorkerInterval,
          thumbnailMaxRetries: settings.thumbnailMaxRetries,
          thumbnailHighLoadMode: settings.thumbnailHighLoadMode,
          thumbnailConcurrentJobs: settings.thumbnailConcurrentJobs,
          thumbnailMemoryLimit: settings.thumbnailMemoryLimit,
        }
        setOriginalSettings(updatedSettings)

        // REMOVED: Force fetch that was causing UI reversion
        // setTimeout(() => {
        //   fetchSettings(true)
        // }, 500)
      }

      return changedSettings.length > 0
    } catch (error) {
      console.error("Failed to save settings:", error)
      setError(error instanceof Error ? error.message : "Save failed")

      // Show error notification
      toast.error("❌ Failed to save settings", {
        description:
          error instanceof Error ? error.message : "Please try again",
        duration: 5000,
      })

      return false
    } finally {
      setSaving(false)
    }
  }, [
    detectChangedSettings,
    updateMultipleSettings,
    setApiKeyModified,
    setOpenWeatherApiKey,
  ])

  useEffect(() => {
    // Always fetch fresh settings on mount
    fetchSettings(true)
  }, []) // Empty dependency array - only run on mount

  const value: SettingsContextType = {
    ...settings,
    loading,
    saving,
    error,
    hasUnsavedChanges,
    updateSetting,
    updateMultipleSettings,
    getSetting,
    deleteSetting,
    saveAllSettings,
    refetch: () => fetchSettings(true),

    // Setters
    setTimezone,
    setEnableThumbnailGeneration,
    setSmallGenerationMode,
    setPurgeSmalllsOnCompletion,
    setImageCaptureType,
    setOpenWeatherApiKey,
    setApiKeyModified,
    setWeatherIntegrationEnabled,
    setWeatherRecordData,
    setSunriseSunsetEnabled,
    setTemperatureUnit,
    setLatitude,
    setLongitude,
    setDbLogRetentionDays,
    setMaxLogFileSize,
    setDbLogLevel,
    setFileLogRetentionDays,
    setFileLogLevel,
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
    setThumbnailJobBatchSize,
    setThumbnailWorkerInterval,
    setThumbnailMaxRetries,
    setThumbnailHighLoadMode,
    setThumbnailConcurrentJobs,
    setThumbnailMemoryLimit,
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

// Lightweight hook for components that only need timezone
export function useTimezoneSettings() {
  const { timezone, loading } = useSettings()
  return { timezone, loading }
}

// Hook for components that need extended settings functionality
export function useSettingsActions() {
  const {
    saveAllSettings,
    updateSetting,
    updateMultipleSettings,
    saving,
    error,
    refetch,
  } = useSettings()

  return {
    saveAllSettings,
    updateSetting,
    updateMultipleSettings,
    saving,
    error,
    refetch,
  }
}

// Hook for weather-related settings
export function useWeatherSettings() {
  const {
    weatherIntegrationEnabled,
    weatherRecordData,
    sunriseSunsetEnabled,
    temperatureUnit,
    latitude,
    longitude,
    openWeatherApiKey,
    apiKeyModified,
    originalApiKeyHash,
    setWeatherIntegrationEnabled,
    setWeatherRecordData,
    setSunriseSunsetEnabled,
    setTemperatureUnit,
    setLatitude,
    setLongitude,
    setOpenWeatherApiKey,
    setApiKeyModified,
  } = useSettings()

  return {
    weatherIntegrationEnabled,
    weatherRecordData,
    sunriseSunsetEnabled,
    temperatureUnit,
    latitude,
    longitude,
    openWeatherApiKey,
    apiKeyModified,
    originalApiKeyHash,
    setWeatherIntegrationEnabled,
    setWeatherRecordData,
    setSunriseSunsetEnabled,
    setTemperatureUnit,
    setLatitude,
    setLongitude,
    setOpenWeatherApiKey,
    setApiKeyModified,
  }
}
