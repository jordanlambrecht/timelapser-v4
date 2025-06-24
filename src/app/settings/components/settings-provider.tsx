"use client"

import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react"
import { toast } from "@/lib/toast"

interface SettingsState {
  // Core settings
  captureInterval: number
  timezone: string
  generateThumbnails: boolean
  imageCaptureType: "PNG" | "JPG"

  // API settings
  openWeatherApiKey: string
  apiKeyModified: boolean

  // Logging settings
  logRetentionDays: number
  maxLogFileSize: number
  enableDebugLogging: boolean
  logLevel: string
  enableLogRotation: boolean
  enableLogCompression: boolean
  maxLogFiles: number

  // UI state
  loading: boolean
  saving: boolean
}

interface SettingsActions {
  // Core settings
  setCaptureInterval: (value: number) => void
  setTimezone: (value: string) => void
  setGenerateThumbnails: (value: boolean) => void

  // Image settings
  setImageCaptureType: (value: "PNG" | "JPG") => void

  // API Keys
  setOpenWeatherApiKey: (value: string) => void

  // Logging settings
  setLogRetentionDays: (value: number) => void
  setMaxLogFileSize: (value: number) => void
  setEnableDebugLogging: (value: boolean) => void
  setLogLevel: (value: string) => void
  setEnableLogRotation: (value: boolean) => void
  setEnableLogCompression: (value: boolean) => void
  setMaxLogFiles: (value: number) => void

  // Actions
  saveSettings: () => Promise<void>
  fetchSettings: () => Promise<void>
}

type SettingsContextType = SettingsState & SettingsActions

const SettingsContext = createContext<SettingsContextType | undefined>(
  undefined
)

const initialState: SettingsState = {
  captureInterval: 300,
  timezone: "America/Chicago",
  generateThumbnails: true,
  imageCaptureType: "JPG",
  openWeatherApiKey: "",
  apiKeyModified: false,
  logRetentionDays: 30,
  maxLogFileSize: 100,
  enableDebugLogging: false,
  logLevel: "info",
  enableLogRotation: true,
  enableLogCompression: false,
  maxLogFiles: 10,
  loading: true,
  saving: false,
}

interface SettingsProviderProps {
  children: ReactNode
}

export function SettingsProvider({ children }: SettingsProviderProps) {
  const [state, setState] = useState<SettingsState>(initialState)

  // Fetch settings on mount
  useEffect(() => {
    fetchSettings()
  }, [])

  const fetchSettings = async () => {
    try {
      setState((prev) => ({ ...prev, loading: true }))

      const response = await fetch("/api/settings")
      if (!response.ok) {
        throw new Error(`Failed to fetch settings: ${response.statusText}`)
      }

      const settings = await response.json()

      setState((prev) => ({
        ...prev,
        captureInterval: parseInt(settings.capture_interval || "300", 10),
        timezone: settings.timezone || "America/Chicago",
        generateThumbnails: settings.generate_thumbnails === "true",
        imageCaptureType: settings.image_capture_type || "JPG",
        openWeatherApiKey: "", // Never populate from server for security
        apiKeyModified: false,
        logRetentionDays: parseInt(settings.log_retention_days || "30", 10),
        maxLogFileSize: parseInt(settings.max_log_file_size || "100", 10),
        enableDebugLogging: settings.enable_debug_logging === "true",
        logLevel: settings.log_level || "info",
        enableLogRotation: settings.enable_log_rotation === "true",
        enableLogCompression: settings.enable_log_compression === "true",
        maxLogFiles: parseInt(settings.max_log_files || "10", 10),
        loading: false,
      }))
    } catch (error) {
      console.error("Failed to fetch settings:", error)
      toast.error("Failed to load settings", {
        description: error instanceof Error ? error.message : "Unknown error",
      })
      setState((prev) => ({ ...prev, loading: false }))
    }
  }

  const saveSettings = async () => {
    try {
      setState((prev) => ({ ...prev, saving: true }))

      const updates = [
        { key: "capture_interval", value: state.captureInterval.toString() },
        { key: "timezone", value: state.timezone },
        {
          key: "generate_thumbnails",
          value: state.generateThumbnails.toString(),
        },
        { key: "image_capture_type", value: state.imageCaptureType },
        { key: "log_retention_days", value: state.logRetentionDays.toString() },
        { key: "max_log_file_size", value: state.maxLogFileSize.toString() },
        {
          key: "enable_debug_logging",
          value: state.enableDebugLogging.toString(),
        },
        { key: "log_level", value: state.logLevel },
        {
          key: "enable_log_rotation",
          value: state.enableLogRotation.toString(),
        },
        {
          key: "enable_log_compression",
          value: state.enableLogCompression.toString(),
        },
        { key: "max_log_files", value: state.maxLogFiles.toString() },
      ]

      // Only include API key if it was modified
      if (state.apiKeyModified && state.openWeatherApiKey.trim()) {
        updates.push({
          key: "openweather_api_key",
          value: state.openWeatherApiKey,
        })
      }

      for (const update of updates) {
        const response = await fetch("/api/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(update),
        })

        if (!response.ok) {
          const errorText = await response.text()
          throw new Error(`Failed to save ${update.key}: ${errorText}`)
        }
      }

      // Reset API key state after successful save
      setState((prev) => ({
        ...prev,
        apiKeyModified: false,
        openWeatherApiKey: "",
        saving: false,
      }))

      toast.success("Settings saved successfully")
    } catch (error) {
      console.error("Failed to save settings:", error)
      toast.error("Failed to save settings", {
        description: error instanceof Error ? error.message : "Unknown error",
      })
      setState((prev) => ({ ...prev, saving: false }))
    }
  }

  const contextValue: SettingsContextType = {
    ...state,

    // Core settings
    setCaptureInterval: (value: number) =>
      setState((prev) => ({ ...prev, captureInterval: value })),
    setTimezone: (value: string) =>
      setState((prev) => ({ ...prev, timezone: value })),
    setGenerateThumbnails: (value: boolean) =>
      setState((prev) => ({ ...prev, generateThumbnails: value })),

    // Image settings
    setImageCaptureType: (value: "PNG" | "JPG") =>
      setState((prev) => ({ ...prev, imageCaptureType: value })),

    // API Keys
    setOpenWeatherApiKey: (value: string) =>
      setState((prev) => ({
        ...prev,
        openWeatherApiKey: value,
        apiKeyModified: true,
      })),

    // Logging settings
    setLogRetentionDays: (value: number) =>
      setState((prev) => ({ ...prev, logRetentionDays: value })),
    setMaxLogFileSize: (value: number) =>
      setState((prev) => ({ ...prev, maxLogFileSize: value })),
    setEnableDebugLogging: (value: boolean) =>
      setState((prev) => ({ ...prev, enableDebugLogging: value })),
    setLogLevel: (value: string) =>
      setState((prev) => ({ ...prev, logLevel: value })),
    setEnableLogRotation: (value: boolean) =>
      setState((prev) => ({ ...prev, enableLogRotation: value })),
    setEnableLogCompression: (value: boolean) =>
      setState((prev) => ({ ...prev, enableLogCompression: value })),
    setMaxLogFiles: (value: number) =>
      setState((prev) => ({ ...prev, maxLogFiles: value })),

    // Actions
    saveSettings,
    fetchSettings: fetchSettings,
  }

  return (
    <SettingsContext.Provider value={contextValue}>
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
