// src/app/settings/hooks/use-settings.ts
"use client"

import { useState, useEffect, useCallback } from "react"
import { toast } from "@/lib/toast"
import { type SettingsActions, type SettingsState } from "@/types"

export function useSettings(): SettingsState & SettingsActions {
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  // Core settings
  const [captureInterval, setCaptureInterval] = useState(300)
  const [timezone, setTimezone] = useState("America/Chicago")
  const [generateThumbnails, setGenerateThumbnails] = useState(true)
  const [imageCaptureType, setImageCaptureType] = useState<"PNG" | "JPG">("JPG")

  // API settings
  const [openWeatherApiKey, setOpenWeatherApiKey] = useState("")
  const [apiKeyModified, setApiKeyModified] = useState(false)
  const [originalApiKeyHash, setOriginalApiKeyHash] = useState("")

  // Logging settings
  const [logRetentionDays, setLogRetentionDays] = useState(30)
  const [maxLogFileSize, setMaxLogFileSize] = useState(100)
  const [enableDebugLogging, setEnableDebugLogging] = useState(false)
  const [logLevel, setLogLevel] = useState("info")
  const [enableLogRotation, setEnableLogRotation] = useState(true)
  const [enableLogCompression, setEnableLogCompression] = useState(false)
  const [maxLogFiles, setMaxLogFiles] = useState(10)

  const fetchSettings = useCallback(async () => {
    console.log("🔄 Fetching settings from API...")
    try {
      const response = await fetch("/api/settings/", { cache: "no-store" })
      const data = await response.json()
      console.log("📥 Received settings:", data)

      setSettings(data)
      setCaptureInterval(parseInt(data.capture_interval || "300"))
      setTimezone(data.timezone || "America/Chicago")
      setGenerateThumbnails(data.generate_thumbnails !== "false")
      setImageCaptureType((data.image_capture_type || "JPG") as "PNG" | "JPG")

      // Handle API key specially
      const apiKeyHash = data.openweather_api_key_hash || ""
      setOriginalApiKeyHash(apiKeyHash)
      if (apiKeyHash && !apiKeyModified) {
        setOpenWeatherApiKey("")
      }

      // Logging settings
      setLogRetentionDays(parseInt(data.log_retention_days || "30"))
      setMaxLogFileSize(parseInt(data.max_log_file_size || "100"))
      setEnableDebugLogging(data.enable_debug_logging === "true")
      setLogLevel(data.log_level || "info")
      setEnableLogRotation(data.enable_log_rotation !== "false")
      setEnableLogCompression(data.enable_log_compression === "true")
      setMaxLogFiles(parseInt(data.max_log_files || "10"))

      console.log("✅ Settings state updated")
    } catch (error) {
      console.error("❌ Failed to fetch settings:", error)
    } finally {
      setLoading(false)
    }
  }, [apiKeyModified])

  const saveSettings = useCallback(async () => {
    setSaving(true)

    try {
      const updates = [
        { key: "capture_interval", value: captureInterval.toString() },
        { key: "timezone", value: timezone },
        { key: "generate_thumbnails", value: generateThumbnails.toString() },
        { key: "image_capture_type", value: imageCaptureType },
        { key: "log_retention_days", value: logRetentionDays.toString() },
        { key: "max_log_file_size", value: maxLogFileSize.toString() },
        { key: "enable_debug_logging", value: enableDebugLogging.toString() },
        { key: "log_level", value: logLevel },
        { key: "enable_log_rotation", value: enableLogRotation.toString() },
        {
          key: "enable_log_compression",
          value: enableLogCompression.toString(),
        },
        { key: "max_log_files", value: maxLogFiles.toString() },
      ]

      // Only include API key if modified
      if (apiKeyModified && openWeatherApiKey.trim()) {
        updates.push({ key: "openweather_api_key", value: openWeatherApiKey })
      }

      const changedSettings: string[] = []
      const currentSettings = {
        capture_interval: settings["capture_interval"] || "",
        timezone: settings["timezone"] || "",
        generate_thumbnails: settings["generate_thumbnails"] || "",
        image_capture_type: settings["image_capture_type"] || "",
        openweather_api_key_hash: settings["openweather_api_key_hash"] || "",
        log_retention_days: settings["log_retention_days"] || "",
        max_log_file_size: settings["max_log_file_size"] || "",
        enable_debug_logging: settings["enable_debug_logging"] || "",
        log_level: settings["log_level"] || "",
        enable_log_rotation: settings["enable_log_rotation"] || "",
        enable_log_compression: settings["enable_log_compression"] || "",
        max_log_files: settings["max_log_files"] || "",
      }

      for (const update of updates) {
        let currentValue =
          currentSettings[update.key as keyof typeof currentSettings]
        let newValue = update.value

        if (update.key === "openweather_api_key") {
          currentValue = ""
        }

        currentValue = String(currentValue || "")
        newValue = String(newValue || "")

        if (currentValue !== newValue) {
          changedSettings.push(update.key)
        }

        const response = await fetch("/api/settings/", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(update),
        })

        if (!response.ok) {
          const errorText = await response.text()
          throw new Error(
            `Failed to save ${update.key}: ${response.status} ${response.statusText} - ${errorText}`
          )
        }
      }

      // Show success toast
      if (changedSettings.length > 0) {
        const settingNames = changedSettings.map((key) => {
          switch (key) {
            case "capture_interval":
              return "capture interval"
            case "timezone":
              return "timezone"
            case "generate_thumbnails":
              return "thumbnail settings"
            case "image_capture_type":
              return "image format"
            case "openweather_api_key":
              return "OpenWeather API key"
            case "log_retention_days":
              return "log retention"
            case "max_log_file_size":
              return "max log file size"
            case "enable_debug_logging":
              return "debug logging"
            case "log_level":
              return "log level"
            case "enable_log_rotation":
              return "log rotation"
            case "enable_log_compression":
              return "log compression"
            case "max_log_files":
              return "max log files"
            default:
              return key.replace(/_/g, " ")
          }
        })

        const message =
          settingNames.length === 1
            ? `${
                settingNames[0].charAt(0).toUpperCase() +
                settingNames[0].slice(1)
              } updated successfully!`
            : `${settingNames.slice(0, -1).join(", ")} and ${settingNames.slice(
                -1
              )} updated successfully!`

        toast.success("Settings saved", {
          description: message,
          duration: 4000,
        })
      } else {
        toast.success("Settings saved", {
          description: "No changes were made",
          duration: 3000,
        })
      }

      await fetchSettings()

      // Reset API key modification flag
      if (apiKeyModified && openWeatherApiKey.trim()) {
        setApiKeyModified(false)
        setOpenWeatherApiKey("")
      }
    } catch (error: unknown) {
      console.error("❌ Failed to save settings:", error)
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error occurred"

      toast.error("Failed to save settings", {
        description: errorMessage,
        duration: 6000,
      })
    } finally {
      setSaving(false)
    }
  }, [
    captureInterval,
    timezone,
    generateThumbnails,
    imageCaptureType,
    logRetentionDays,
    maxLogFileSize,
    enableDebugLogging,
    logLevel,
    enableLogRotation,
    enableLogCompression,
    maxLogFiles,
    openWeatherApiKey,
    apiKeyModified,
    settings,
    fetchSettings,
  ])

  useEffect(() => {
    fetchSettings()
  }, [fetchSettings])

  return {
    // State
    captureInterval,
    timezone,
    generateThumbnails,
    imageCaptureType,
    openWeatherApiKey,
    apiKeyModified,
    originalApiKeyHash,
    logRetentionDays,
    maxLogFileSize,
    enableDebugLogging,
    logLevel,
    enableLogRotation,
    enableLogCompression,
    maxLogFiles,
    loading,
    saving,

    // Actions
    setCaptureInterval,
    setTimezone,
    setGenerateThumbnails,
    setImageCaptureType,
    setOpenWeatherApiKey,
    setApiKeyModified,
    setOriginalApiKeyHash,
    setLogRetentionDays,
    setMaxLogFileSize,
    setEnableDebugLogging,
    setLogLevel,
    setEnableLogRotation,
    setEnableLogCompression,
    setMaxLogFiles,
    fetchSettings,
    saveSettings,
  }
}
