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

  // Corruption detection settings
  const [corruptionDetectionEnabled, setCorruptionDetectionEnabled] =
    useState(true)
  const [corruptionScoreThreshold, setCorruptionScoreThreshold] = useState(70)
  const [corruptionAutoDiscardEnabled, setCorruptionAutoDiscardEnabled] =
    useState(false)
  const [corruptionAutoDisableDegraded, setCorruptionAutoDisableDegraded] =
    useState(false)
  const [
    corruptionDegradedConsecutiveThreshold,
    setCorruptionDegradedConsecutiveThreshold,
  ] = useState(10)
  const [
    corruptionDegradedTimeWindowMinutes,
    setCorruptionDegradedTimeWindowMinutes,
  ] = useState(30)
  const [
    corruptionDegradedFailurePercentage,
    setCorruptionDegradedFailurePercentage,
  ] = useState(50)
  const [corruptionHeavyDetectionEnabled, setCorruptionHeavyDetectionEnabled] =
    useState(false)

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

      // Fetch corruption settings separately
      try {
        const corruptionResponse = await fetch("/api/corruption/settings", {
          cache: "no-store",
        })
        const corruptionData = await corruptionResponse.json()

        if (corruptionData.global_settings) {
          const global = corruptionData.global_settings
          setCorruptionDetectionEnabled(
            global.corruption_detection_enabled !== false
          )
          setCorruptionScoreThreshold(
            parseInt(global.corruption_score_threshold || "70")
          )
          setCorruptionAutoDiscardEnabled(
            global.corruption_auto_discard_enabled === true
          )
          setCorruptionAutoDisableDegraded(
            global.corruption_auto_disable_degraded === true
          )
          setCorruptionDegradedConsecutiveThreshold(
            parseInt(global.corruption_degraded_consecutive_threshold || "10")
          )
          setCorruptionDegradedTimeWindowMinutes(
            parseInt(global.corruption_degraded_time_window_minutes || "30")
          )
          setCorruptionDegradedFailurePercentage(
            parseInt(global.corruption_degraded_failure_percentage || "50")
          )
        }

        // Check if any camera has heavy detection enabled
        if (corruptionData.camera_settings) {
          const hasHeavyDetection = Object.values(
            corruptionData.camera_settings
          ).some((camera: any) => camera.corruption_detection_heavy === true)
          setCorruptionHeavyDetectionEnabled(hasHeavyDetection)
        }
      } catch (corruptionError) {
        console.error(
          "❌ Failed to fetch corruption settings:",
          corruptionError
        )
      }

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

          // Only make API call if value actually changed
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
      }

      // Save corruption detection settings separately
      const corruptionSettings = {
        global_settings: {
          corruption_detection_enabled: corruptionDetectionEnabled,
          corruption_score_threshold: corruptionScoreThreshold,
          corruption_auto_discard_enabled: corruptionAutoDiscardEnabled,
          corruption_auto_disable_degraded: corruptionAutoDisableDegraded,
          corruption_degraded_consecutive_threshold:
            corruptionDegradedConsecutiveThreshold,
          corruption_degraded_time_window_minutes:
            corruptionDegradedTimeWindowMinutes,
          corruption_degraded_failure_percentage:
            corruptionDegradedFailurePercentage,
        },
        camera_settings: {
          // For now, apply heavy detection setting to all cameras
          // This could be enhanced later to be per-camera
          heavy_detection_enabled: corruptionHeavyDetectionEnabled,
        },
      }

      // Check if corruption settings have actually changed
      let corruptionSettingsChanged = false
      try {
        const currentCorruptionResponse = await fetch(
          "/api/corruption/settings",
          {
            cache: "no-store",
          }
        )
        const currentCorruptionData = await currentCorruptionResponse.json()

        if (currentCorruptionData.global_settings) {
          const current = currentCorruptionData.global_settings
          const newSettings = corruptionSettings.global_settings

          // Compare each corruption setting
          corruptionSettingsChanged =
            current.corruption_detection_enabled !==
              newSettings.corruption_detection_enabled ||
            current.corruption_score_threshold !==
              newSettings.corruption_score_threshold ||
            current.corruption_auto_discard_enabled !==
              newSettings.corruption_auto_discard_enabled ||
            current.corruption_auto_disable_degraded !==
              newSettings.corruption_auto_disable_degraded ||
            current.corruption_degraded_consecutive_threshold !==
              newSettings.corruption_degraded_consecutive_threshold ||
            current.corruption_degraded_time_window_minutes !==
              newSettings.corruption_degraded_time_window_minutes ||
            current.corruption_degraded_failure_percentage !==
              newSettings.corruption_degraded_failure_percentage
        }

        // Also check camera settings for heavy detection changes
        if (
          !corruptionSettingsChanged &&
          currentCorruptionData.camera_settings
        ) {
          const currentHeavyDetectionStates = Object.values(
            currentCorruptionData.camera_settings
          ).map((camera: any) => camera.corruption_detection_heavy)
          const allCurrentlyHeavy = currentHeavyDetectionStates.every(
            (state) => state === true
          )
          const allCurrentlyLight = currentHeavyDetectionStates.every(
            (state) => state === false
          )

          // If we're setting all to heavy but not all are currently heavy, or vice versa
          if (
            (corruptionHeavyDetectionEnabled && !allCurrentlyHeavy) ||
            (!corruptionHeavyDetectionEnabled && !allCurrentlyLight)
          ) {
            corruptionSettingsChanged = true
          }
        }
      } catch (error) {
        console.error(
          "Failed to fetch current corruption settings for comparison:",
          error
        )
        // If we can't fetch current settings, assume they changed to be safe
        corruptionSettingsChanged = true
      }

      if (corruptionSettingsChanged) {
        const corruptionResponse = await fetch("/api/corruption/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(corruptionSettings),
        })

        if (!corruptionResponse.ok) {
          const errorText = await corruptionResponse.text()
          throw new Error(
            `Failed to save corruption settings: ${corruptionResponse.status} ${corruptionResponse.statusText} - ${errorText}`
          )
        }

        // Only add to changed settings list if API call was made
        changedSettings.push("corruption_detection_settings")
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
            case "corruption_detection_settings":
              return "corruption detection settings"
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
    corruptionDetectionEnabled,
    corruptionScoreThreshold,
    corruptionAutoDiscardEnabled,
    corruptionAutoDisableDegraded,
    corruptionDegradedConsecutiveThreshold,
    corruptionDegradedTimeWindowMinutes,
    corruptionDegradedFailurePercentage,
    corruptionHeavyDetectionEnabled,
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
    corruptionDetectionEnabled,
    corruptionScoreThreshold,
    corruptionAutoDiscardEnabled,
    corruptionAutoDisableDegraded,
    corruptionDegradedConsecutiveThreshold,
    corruptionDegradedTimeWindowMinutes,
    corruptionDegradedFailurePercentage,
    corruptionHeavyDetectionEnabled,
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
    setCorruptionDetectionEnabled,
    setCorruptionScoreThreshold,
    setCorruptionAutoDiscardEnabled,
    setCorruptionAutoDisableDegraded,
    setCorruptionDegradedConsecutiveThreshold,
    setCorruptionDegradedTimeWindowMinutes,
    setCorruptionDegradedFailurePercentage,
    setCorruptionHeavyDetectionEnabled,
    fetchSettings,
    saveSettings,
  }
}
