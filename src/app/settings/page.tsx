// src/app/settings/page.tsx
"use client"

import { useState, useEffect } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"

import { ImageTypeSlider } from "@/components/ui/image-type-slider"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Settings as SettingsIcon,
  Clock,
  Save,
  RefreshCw,
  Globe,
  Image as ImageIcon,
  AlertTriangle,
  Trash2,
  RotateCcw,
  FileText,
  Cloud,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { PasswordInput } from "@/components/ui/password-input"
import { NumberInput } from "@/components/ui/number-input"
import { TimezoneSelector } from "@/components/timezone-selector-combobox"
import { ThumbnailRegenerationModal } from "@/components/thumbnail-regeneration-modal"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { toast } from "@/lib/toast"
import SwitchLabeled from "@/components/ui/switch-labeled"

export default function Settings() {
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [captureInterval, setCaptureInterval] = useState(300)
  const [timezone, setTimezone] = useState("America/Chicago")
  const [generateThumbnails, setGenerateThumbnails] = useState(true)
  const [thumbnailModalOpen, setThumbnailModalOpen] = useState(false)
  const [thumbnailConfirmOpen, setThumbnailConfirmOpen] = useState(false)

  // TODO: New settings state variables (Not Implemented)
  const [imageCaptureType, setImageCaptureType] = useState<"PNG" | "JPG">("JPG") // "PNG" or "JPG"
  const [openWeatherApiKey, setOpenWeatherApiKey] = useState("")
  const [showApiKey, setShowApiKey] = useState(false)
  const [apiKeyModified, setApiKeyModified] = useState(false)
  const [originalApiKeyHash, setOriginalApiKeyHash] = useState("")
  const [imageConversionDialogOpen, setImageConversionDialogOpen] =
    useState(false)
  const [imageFormatChangeDialogOpen, setImageFormatChangeDialogOpen] =
    useState(false)
  const [pendingImageFormat, setPendingImageFormat] = useState<"PNG" | "JPG">(
    "JPG"
  )

  // Logging settings state variables (Not Implemented)
  const [logRetentionDays, setLogRetentionDays] = useState(30)
  const [maxLogFileSize, setMaxLogFileSize] = useState(100) // MB
  const [enableDebugLogging, setEnableDebugLogging] = useState(false)
  const [logLevel, setLogLevel] = useState("info") // debug, info, warn, error
  const [enableLogRotation, setEnableLogRotation] = useState(true)
  const [enableLogCompression, setEnableLogCompression] = useState(false)
  const [maxLogFiles, setMaxLogFiles] = useState(10) // Number of rotated files to keep

  // Confirmation dialogs for danger zone actions
  const [cleanLogsConfirmOpen, setCleanLogsConfirmOpen] = useState(false)
  const [resetSystemConfirmOpen, setResetSystemConfirmOpen] = useState(false)
  const [resetSettingsConfirmOpen, setResetSettingsConfirmOpen] =
    useState(false)
  const [deleteAllCamerasConfirmOpen, setDeleteAllCamerasConfirmOpen] =
    useState(false)
  const [deleteAllImagesConfirmOpen, setDeleteAllImagesConfirmOpen] =
    useState(false)
  const [deleteAllTimelapsesConfirmOpen, setDeleteAllTimelapsesConfirmOpen] =
    useState(false)
  const [deleteAllThumbnailsConfirmOpen, setDeleteAllThumbnailsConfirmOpen] =
    useState(false)

  // Debug timezone changes
  const handleTimezoneChange = (newTimezone: string) => {
    console.log(
      "🎯 Settings page: timezone changing from",
      timezone,
      "to",
      newTimezone
    )
    setTimezone(newTimezone)
  }

  useEffect(() => {
    fetchSettings()
  }, [])

  const fetchSettings = async () => {
    console.log("🔄 Fetching settings from API...")
    try {
      const response = await fetch("/api/settings/", { cache: "no-store" })
      const data = await response.json()
      console.log("📥 Received settings:", data)

      setSettings(data)
      setCaptureInterval(parseInt(data.capture_interval || "300"))
      setTimezone(data.timezone || "America/Chicago")
      setGenerateThumbnails(data.generate_thumbnails !== "false") // Default true unless explicitly false

      // TODO: features not implemented yet, but settings are stored:
      setImageCaptureType((data.image_capture_type || "JPG") as "PNG" | "JPG")

      // Handle API key specially - store hash for comparison but show placeholder
      const apiKeyHash = data.openweather_api_key_hash || ""
      setOriginalApiKeyHash(apiKeyHash)
      if (apiKeyHash && !apiKeyModified) {
        // Show masked placeholder for existing API key
        setOpenWeatherApiKey("") // Keep field empty until user starts typing
      }

      setLogRetentionDays(parseInt(data.log_retention_days || "30"))
      setMaxLogFileSize(parseInt(data.max_log_file_size || "100"))
      setEnableDebugLogging(data.enable_debug_logging === "true")
      setLogLevel(data.log_level || "info")
      setEnableLogRotation(data.enable_log_rotation !== "false") // Default true unless explicitly false
      setEnableLogCompression(data.enable_log_compression === "true")
      setMaxLogFiles(parseInt(data.max_log_files || "10"))

      console.log("✅ Settings state updated:", {
        captureInterval: parseInt(data.capture_interval || "300"),
        timezone: data.timezone || "America/Chicago",
        generateThumbnails: data.generate_thumbnails !== "false",
        imageCaptureType: data.image_capture_type || "JPG",
        logRetentionDays: parseInt(data.log_retention_days || "30"),
        logLevel: data.log_level || "info",
      })
    } catch (error) {
      console.error("❌ Failed to fetch settings:", error)
    } finally {
      setLoading(false)
    }
  }

  const saveSettings = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)

    console.log("💾 Saving settings:", {
      captureInterval,
      timezone,
      generateThumbnails,
    })

    try {
      // Prepare all settings for saving (settings are saved but features may not be implemented yet)
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

      // Only include API key if it has been modified and has a value
      if (apiKeyModified && openWeatherApiKey.trim()) {
        updates.push({ key: "openweather_api_key", value: openWeatherApiKey })
      }

      console.log("🔄 Updates to save:", updates)

      // Track which settings actually changed
      const changedSettings: string[] = []

      // Normalize current settings for comparison
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
        console.log(`📤 Saving ${update.key}:`, update.value)

        // Check if the value actually changed
        let currentValue =
          currentSettings[update.key as keyof typeof currentSettings]
        let newValue = update.value

        // Special handling for API key comparison
        if (update.key === "openweather_api_key") {
          // If we reach here, the API key was modified and should be saved
          currentValue = "" // Mark as changed since we only include it when modified
        }

        // Normalize values for comparison (convert to strings)
        currentValue = String(currentValue || "")
        newValue = String(newValue || "")

        console.log(`🔍 Comparing ${update.key}:`, {
          currentValue,
          newValue,
          changed: currentValue !== newValue,
        })

        if (currentValue !== newValue) {
          changedSettings.push(update.key)
        }

        // Add more detailed logging for debugging
        const requestUrl = "/api/settings/"
        const requestOptions = {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(update),
        }

        console.log(`🔍 Request details for ${update.key}:`, {
          url: requestUrl,
          method: requestOptions.method,
          headers: requestOptions.headers,
          body: update,
        })

        const response = await fetch(requestUrl, requestOptions)

        console.log(
          `📥 Response for ${update.key}:`,
          response.status,
          response.statusText,
          response.ok
        )

        if (!response.ok) {
          const errorText = await response.text()
          console.error(`❌ Failed to save ${update.key}:`, {
            status: response.status,
            statusText: response.statusText,
            errorText,
            headers: Object.fromEntries(response.headers.entries()),
          })
          throw new Error(
            `Failed to save ${update.key}: ${response.status} ${response.statusText} - ${errorText}`
          )
        }

        const result = await response.json()
        console.log(`✅ Saved ${update.key} successfully:`, result)
      }

      // Show dynamic success toast based on what changed
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

      console.log("🔄 Fetching updated settings...")
      await fetchSettings()

      // Reset API key modification flag after successful save
      if (apiKeyModified && openWeatherApiKey.trim()) {
        setApiKeyModified(false)
        setOpenWeatherApiKey("") // Clear the field so it shows placeholder again
      }
    } catch (error: unknown) {
      console.error("❌ Failed to save settings:", error)
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error occurred"

      // Show error toast
      toast.error("Failed to save settings", {
        description: errorMessage,
        duration: 6000,
      })
    } finally {
      setSaving(false)
    }
  }

  const formatInterval = (seconds: number) => {
    const sec = seconds
    if (sec < 60) return `${sec} seconds`
    if (sec < 3600) return `${Math.floor(sec / 60)} minutes`
    return `${Math.floor(sec / 3600)} hours`
  }

  const getIntervalPreset = (seconds: number) => {
    const sec = seconds
    const presets = [
      { label: "Every 30 seconds", value: 30 },
      { label: "Every minute", value: 60 },
      { label: "Every 5 minutes", value: 300 },
      { label: "Every 15 minutes", value: 900 },
      { label: "Every hour", value: 3600 },
    ]

    return presets.find((p) => p.value === sec)?.label || "Custom interval"
  }

  // TODO: New handlers for added functionality (Not Implemented)
  const handleImageCaptureTypeChange = (newType: "PNG" | "JPG") => {
    setPendingImageFormat(newType)
    setImageFormatChangeDialogOpen(true)
  }

  const handleImageFormatConfirm = () => {
    setImageFormatChangeDialogOpen(false)
    setImageCaptureType(pendingImageFormat)
    setImageConversionDialogOpen(true)
  }

  const handleImageFormatCancel = () => {
    setImageFormatChangeDialogOpen(false)
    setImageCaptureType(pendingImageFormat) // Still change the format, just don't convert existing
  }

  const handleCleanLogsNow = async () => {
    setCleanLogsConfirmOpen(false)
    toast.info("Cleaning logs...", {
      description: "System logs are being cleaned up",
      duration: 3000,
    })
    // TODO: Implement actual log cleanup functionality
  }

  const handleResetSystem = async () => {
    setResetSystemConfirmOpen(false)
    toast.warning("System reset not available", {
      description:
        "This feature requires additional safety measures to implement",
      duration: 5000,
    })
    // TODO: Implement actual system reset functionality
  }

  const handleDeleteAllCameras = async () => {
    setDeleteAllCamerasConfirmOpen(false)
    toast.warning("Bulk delete not available", {
      description: "Use individual camera deletion for safety",
      duration: 4000,
    })
    // TODO: Implement actual bulk camera deletion
  }

  const handleDeleteAllImages = async () => {
    setDeleteAllImagesConfirmOpen(false)
    toast.warning("Bulk image delete not available", {
      description:
        "This feature requires additional safety measures to implement",
      duration: 5000,
    })
    // TODO: Implement actual bulk image deletion
  }

  const handleDeleteAllTimelapses = async () => {
    setDeleteAllTimelapsesConfirmOpen(false)
    toast.warning("Bulk timelapse delete not available", {
      description: "Use individual timelapse deletion for safety",
      duration: 4000,
    })
    // TODO: Implement actual bulk timelapse deletion
  }

  const handleResetSettings = async () => {
    setResetSettingsConfirmOpen(false)
    toast.info("Resetting settings...", {
      description: "All settings will be restored to default values",
      duration: 3000,
    })
    // TODO: Implement actual settings reset functionality
  }

  const handleDeleteAllThumbnails = async () => {
    setDeleteAllThumbnailsConfirmOpen(false)
    toast.info("Deleting thumbnails...", {
      description: "All thumbnail images are being removed",
      duration: 3000,
    })
    // TODO: Implement actual thumbnail deletion functionality
  }

  // Handler for API key input changes
  const handleApiKeyChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setOpenWeatherApiKey(value)
    setApiKeyModified(true) // Mark as modified when user starts typing
  }

  // Handler for when user focuses on the API key field
  const handleApiKeyFocus = () => {
    if (!apiKeyModified && originalApiKeyHash) {
      // Clear the masked value when user focuses to type new key
      setOpenWeatherApiKey("")
      setApiKeyModified(true)
    }
  }

  // Get the display value for the API key input
  const getApiKeyDisplayValue = () => {
    if (apiKeyModified || !originalApiKeyHash) {
      return openWeatherApiKey // Show actual input when modified or no existing key
    }
    // For existing unmodified keys, show a readable placeholder instead of empty
    return (
      "••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••" +
      originalApiKeyHash.slice(-4)
    )
  }

  // Get the placeholder for the API key input
  const getApiKeyPlaceholder = () => {
    if (originalApiKeyHash && !apiKeyModified) {
      return "Click to enter new API key"
    }
    return "Enter your OpenWeather API key"
  }

  // TODO: This needs to be moved to a layout file
  if (loading) {
    return (
      <div className='flex items-center justify-center min-h-[60vh]'>
        <div className='space-y-6 text-center'>
          <div className='relative'>
            <div className='w-16 h-16 mx-auto border-4 rounded-full border-cyan/20 border-t-cyan animate-spin' />
            <div
              className='absolute inset-0 w-16 h-16 mx-auto border-4 rounded-full border-purple/20 border-b-purple-light animate-spin'
              style={{
                animationDirection: "reverse",
                animationDuration: "1.5s",
              }}
            />
            <div
              className='absolute w-12 h-12 mx-auto border-2 rounded-full inset-2 border-pink/30 border-l-pink animate-spin'
              style={{ animationDuration: "2s" }}
            />
          </div>
          <div>
            <p className='font-medium text-white'>Loading settings...</p>
            <p className='mt-1 text-sm text-grey-light/60'>
              Configuring system preferences
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className='max-w-4xl mx-auto space-y-8'>
      {/* Header */}
      <div className='space-y-4'>
        <div>
          <h1 className='text-4xl font-bold gradient-text'>Settings</h1>
          <p className='mt-2 text-muted-foreground'>
            Configure capture intervals and system preferences
          </p>
        </div>
      </div>

      {/* Unified Settings Form */}
      <form onSubmit={saveSettings} className='space-y-6'>
        {/* Capture Settings*/}
        <Card className='transition-all duration-300 glass hover:glow'>
          <CardHeader>
            <CardTitle className='flex items-center space-x-2'>
              <Clock className='w-5 h-5 text-primary' />
              <span>Capture Settings</span>
            </CardTitle>
            <CardDescription>
              Configure image capture intervals and thumbnail generation
            </CardDescription>
          </CardHeader>
          <CardContent className='space-y-6'>
            <div className='space-y-4'>
              <div className='space-y-3 grid grid-cols-1 md:grid-cols-2 gap-x-8'>
                <div>
                  <NumberInput
                    id='interval'
                    label='Interval (seconds)'
                    value={captureInterval}
                    onChange={setCaptureInterval}
                    min={1}
                    max={86400}
                    step={1}
                    className='bg-background/50 border-borderColor/50 focus:border-primary/50'
                  />
                  <div className='flex flex-col space-x-4'>
                    <Badge
                      variant='outline'
                      className='px-2 py-2 whitespace-nowrap'
                    >
                      ({formatInterval(captureInterval)})
                    </Badge>
                  </div>
                  <p className='text-xs text-muted-foreground'>
                    Range: 1 second to 24 hours (86,400 seconds)
                  </p>
                </div>

                {/* Quick Presets */}
                <div className='space-y-4'>
                  <Label className='text-xs text-muted-foreground'>
                    Quick Presets:
                  </Label>
                  <div className='grid grid-cols-2 sm:grid-cols-3 md:grid-cols-2 gap-2'>
                    {[
                      { label: "30s", value: 30, desc: "High detail" },
                      { label: "1m", value: 60, desc: "Detailed" },
                      { label: "5m", value: 300, desc: "Standard" },
                      { label: "15m", value: 900, desc: "Moderate" },
                      { label: "1h", value: 3600, desc: "Long-term" },
                      { label: "2h", value: 7200, desc: "Longer-term" },
                    ].map((preset) => (
                      <Button
                        key={preset.value}
                        type='button'
                        variant='outline'
                        size='sm'
                        onClick={() => setCaptureInterval(preset.value)}
                        className={cn(
                          "text-xs h-8 px-2 border-borderColor/50 hover:border-primary/50 transition-all duration-300 ease-in-out",
                          captureInterval === preset.value
                            ? "bg-primary border-primary/50 text-blue"
                            : "bg-background/30 text-muted-foreground hover:text-foreground"
                        )}
                        disabled={saving}
                        title={preset.desc}
                      >
                        {preset.label}
                      </Button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Thumbnail Generation Toggle */}
              <div className='space-y-3 my-8'>
                <div className='flex items-center justify-between'>
                  <div className='space-y-1'>
                    <Label
                      htmlFor='thumbnails'
                      className='text-sm font-medium flex items-center space-x-2'
                    >
                      <ImageIcon className='w-4 h-4 text-purple-light' />
                      <h3>Generate Thumbnails</h3>
                    </Label>
                    <p className='text-xs text-muted-foreground'>
                      Create small preview images for faster dashboard loading
                    </p>
                  </div>
                  <SwitchLabeled
                    id='thumbnails'
                    falseLabel='disabled'
                    trueLabel='enabled'
                    checked={generateThumbnails}
                    onCheckedChange={setGenerateThumbnails}
                  />
                </div>
                <div className='p-3 rounded-lg bg-background/30 border border-borderColor/30'>
                  <div className='flex items-center space-x-2 text-xs text-muted-foreground'>
                    <div
                      className={cn(
                        "w-2 h-2 rounded-full",
                        generateThumbnails ? "bg-green-500" : "bg-gray-500"
                      )}
                    />
                    <span>
                      {generateThumbnails
                        ? "Thumbnails will be generated for faster dashboard performance"
                        : "Only full-size images will be saved (slower dashboard loading)"}
                    </span>
                  </div>
                  {generateThumbnails && (
                    <div className='mt-2 text-xs text-purple-light/70'>
                      Creates: 200×150 thumbnails + 800×600 small images
                      alongside full captures
                    </div>
                  )}
                  {generateThumbnails && (
                    <div className='mt-3 pt-3 border-t border-borderColor/20'>
                      <Button
                        type='button'
                        variant='outline'
                        size='sm'
                        onClick={() => setThumbnailConfirmOpen(true)}
                        className='text-xs border-cyan-500/50 text-cyan-300 hover:bg-cyan-500/20 hover:text-white hover:border-cyan-400'
                      >
                        <ImageIcon className='w-3 h-3 mr-2' />
                        Regenerate All Now
                      </Button>
                      <p className='mt-2 text-xs text-gray-500'>
                        Generate thumbnails for existing images that don't have
                        them
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Image Capture Type Selection */}
              <div className='space-y-3 my-8'>
                <div className='space-y-1'>
                  <Label className='text-sm font-medium flex items-center space-x-2'>
                    <ImageIcon className='w-4 h-4 text-blue-400' />
                    <span>Image Capture Type</span>
                    <Badge
                      variant='secondary'
                      className='ml-2 text-xs bg-yellow-500/20 text-yellow-300 border-yellow-500/30'
                    >
                      Not Implemented
                    </Badge>
                  </Label>
                  <p className='text-xs text-muted-foreground'>
                    Choose the format for captured images (settings are saved
                    but feature is not active yet)
                  </p>
                </div>
                <ImageTypeSlider
                  value={imageCaptureType}
                  onValueChange={handleImageCaptureTypeChange}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Timezone Settings - Full Width */}
        <Card className='transition-all duration-300 glass hover:glow'>
          <CardHeader className='mb-2 pb-0'>
            <CardTitle className='flex items-center space-x-2'>
              <Globe className='w-5 h-5 text-pink' />
              <span className='text-white'>Timezone Configuration</span>
            </CardTitle>
            <CardDescription>
              Set the timezone for accurate time calculations and display
            </CardDescription>
          </CardHeader>
          <CardContent>
            <TimezoneSelector
              value={timezone}
              onChange={handleTimezoneChange}
              disabled={saving}
            />
          </CardContent>
        </Card>

        {/* Additional Settings Grid */}
        <div className='grid gap-6 lg:grid-cols-2'>
          {/* External Services */}
          <Card className='transition-all duration-300 glass hover:glow'>
            <CardHeader>
              <CardTitle className='flex items-center space-x-2'>
                <Cloud className='w-5 h-5 text-blue-400' />
                <span>External Services</span>
                <Badge
                  variant='secondary'
                  className='ml-2 text-xs bg-yellow-500/20 text-yellow-300 border-yellow-500/30'
                >
                  Not Implemented
                </Badge>
              </CardTitle>
              <CardDescription>
                Configure external API integrations (settings are saved but
                features are not active yet)
              </CardDescription>
            </CardHeader>
            <CardContent className='space-y-4'>
              <div className='space-y-3'>
                <Label
                  htmlFor='openweather-key'
                  className='text-sm font-medium'
                >
                  OpenWeather API Key
                </Label>
                <PasswordInput
                  id='openweather-key'
                  value={getApiKeyDisplayValue()}
                  onChange={handleApiKeyChange}
                  onFocus={handleApiKeyFocus}
                  placeholder={getApiKeyPlaceholder()}
                  className='bg-background/50 border-borderColor/50 focus:border-primary/50'
                />
                <p className='text-xs text-muted-foreground'>
                  Used for weather overlay data on timelapses
                </p>
              </div>
            </CardContent>
          </Card>

          {/* System Maintenance */}
          <Card className='transition-all duration-300 glass hover:glow'>
            <CardHeader>
              <CardTitle className='flex items-center space-x-2'>
                <FileText className='w-5 h-5 text-green-400' />
                <span>System Maintenance</span>
                <Badge
                  variant='secondary'
                  className='ml-2 text-xs bg-yellow-500/20 text-yellow-300 border-yellow-500/30'
                >
                  Not Implemented
                </Badge>
              </CardTitle>
              <CardDescription>
                Manage system logs and maintenance tasks
              </CardDescription>
            </CardHeader>
            <CardContent className='space-y-4'>
              <div className='space-y-3'>
                <div className='flex items-center justify-between'>
                  <div className='space-y-1'>
                    <Label className='text-sm font-medium'>System Logs</Label>
                    <p className='text-xs text-muted-foreground'>
                      Remove old log files to free up disk space
                    </p>
                  </div>
                  <Button
                    type='button'
                    variant='outline'
                    size='sm'
                    onClick={() => setCleanLogsConfirmOpen(true)}
                    className='border-green-500/50 text-green-300 hover:bg-green-500/20 hover:text-white hover:border-green-400'
                  >
                    <FileText className='w-4 h-4 mr-2' />
                    Clean Logs Now
                  </Button>
                </div>
              </div>

              {/* Log Retention Settings */}
              <div className='space-y-4 p-4 rounded-lg bg-background/30 border border-borderColor/30'>
                <Label className='text-sm font-medium'>Log Configuration</Label>

                <div className='grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4'>
                  <div className='flex flex-col justify-between gap-y-2'>
                    <NumberInput
                      id='log-retention'
                      label='Retention Period (days)'
                      value={logRetentionDays}
                      onChange={setLogRetentionDays}
                      min={1}
                      max={365}
                      className='bg-background/50 border-borderColor/50 focus:border-primary/50'
                    />
                  </div>

                  <div className='flex flex-col justify-between gap-y-2'>
                    <NumberInput
                      id='max-log-size'
                      label='Max File Size (MB)'
                      value={maxLogFileSize}
                      onChange={setMaxLogFileSize}
                      min={1}
                      max={1000}
                      className='bg-background/50 border-borderColor/50 focus:border-primary/50'
                    />
                  </div>

                  <div className='flex flex-col justify-between gap-y-2'>
                    <NumberInput
                      id='max-log-files'
                      label='Max Rotated Files'
                      value={maxLogFiles}
                      onChange={setMaxLogFiles}
                      min={1}
                      max={50}
                      className='bg-background/50 border-borderColor/50 focus:border-primary/50'
                    />
                  </div>
                </div>

                <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
                  <div className='space-y-2'>
                    <Label
                      htmlFor='log-level'
                      className='text-xs text-muted-foreground'
                    >
                      Log Level
                    </Label>
                    <Select value={logLevel} onValueChange={setLogLevel}>
                      <SelectTrigger className='bg-background/50 border-borderColor/50 focus:border-primary/50'>
                        <SelectValue placeholder='Select log level' />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value='debug'>
                          Debug (Most Verbose)
                        </SelectItem>
                        <SelectItem value='info'>Info (Standard)</SelectItem>
                        <SelectItem value='warn'>
                          Warning (Important Only)
                        </SelectItem>
                        <SelectItem value='error'>
                          Error (Critical Only)
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className='space-y-3'>
                  <div className='flex items-center justify-between'>
                    <div className='space-y-1'>
                      <Label
                        htmlFor='debug-logging'
                        className='text-sm font-medium'
                      >
                        Debug Logging
                      </Label>
                      <p className='text-xs text-muted-foreground'>
                        Enable detailed debug information in logs (overrides log
                        level)
                      </p>
                    </div>
                    <SwitchLabeled
                      id='debug-logging'
                      checked={enableDebugLogging}
                      onCheckedChange={setEnableDebugLogging}
                    />
                  </div>

                  <div className='flex items-center justify-between'>
                    <div className='space-y-1'>
                      <Label
                        htmlFor='log-rotation'
                        className='text-sm font-medium'
                      >
                        Log Rotation
                      </Label>
                      <p className='text-xs text-muted-foreground'>
                        Automatically rotate logs when they reach max size
                      </p>
                    </div>
                    <SwitchLabeled
                      id='log-rotation'
                      checked={enableLogRotation}
                      onCheckedChange={setEnableLogRotation}
                    />
                  </div>

                  <div className='flex items-center justify-between'>
                    <div className='space-y-1'>
                      <Label
                        htmlFor='log-compression'
                        className='text-sm font-medium'
                      >
                        Log Compression
                      </Label>
                      <p className='text-xs text-muted-foreground'>
                        Compress rotated log files to save disk space
                      </p>
                    </div>
                    <SwitchLabeled
                      id='log-compression'
                      checked={enableLogCompression}
                      onCheckedChange={setEnableLogCompression}
                    />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/*  Save Button */}
        <div className='flex justify-center pt-4 pb-2'>
          <Button
            type='submit'
            disabled={saving}
            className='transition-colors duration-300 ease-in text-black min-w-[200px] bg-primary hover:bg-primary/80 font-medium'
          >
            {saving ? (
              <>
                <RefreshCw className='w-4 h-4 mr-2 animate-spin' />
                Saving Settings...
              </>
            ) : (
              <>
                <Save className='w-4 h-4 mr-2' />
                Save All Settings
              </>
            )}
          </Button>
        </div>

        {/* Danger Zone - Full Width */}
        <Card className='transition-all duration-300 glass hover:glow border-red-500/30'>
          <CardHeader>
            <CardTitle className='flex items-center space-x-2 text-red-400'>
              <AlertTriangle className='w-5 h-5 text-red-500' />
              <span>Danger Zone</span>
              <Badge
                variant='secondary'
                className='ml-2 text-xs bg-yellow-500/20 text-yellow-300 border-yellow-500/30'
              >
                Not Implemented
              </Badge>
            </CardTitle>
            <CardDescription className='text-red-300/70'>
              Destructive actions that cannot be undone. Use with extreme
              caution.
            </CardDescription>
          </CardHeader>
          <CardContent className='space-y-4'>
            <div className='grid gap-4 md:grid-cols-2 lg:grid-cols-3'>
              <Button
                type='button'
                variant='destructive'
                size='sm'
                onClick={() => setResetSystemConfirmOpen(true)}
                className='bg-red-600/20 border border-red-500/30 text-red-400 hover:bg-red-500/30 hover:text-white'
              >
                <RotateCcw className='w-4 h-4 mr-2' />
                Reset Whole System
              </Button>
              <Button
                type='button'
                variant='destructive'
                size='sm'
                onClick={() => setResetSettingsConfirmOpen(true)}
                className='bg-orange-600/20 border border-orange-500/30 text-orange-400 hover:bg-orange-500/30 hover:text-white'
              >
                <RotateCcw className='w-4 h-4 mr-2' />
                Reset Settings
              </Button>
              <Button
                type='button'
                variant='destructive'
                size='sm'
                onClick={() => setDeleteAllCamerasConfirmOpen(true)}
                className='bg-red-600/20 border border-red-500/30 text-red-400 hover:bg-red-500/30 hover:text-white'
              >
                <Trash2 className='w-4 h-4 mr-2' />
                Delete All Cameras
              </Button>
              <Button
                type='button'
                variant='destructive'
                size='sm'
                onClick={() => setDeleteAllImagesConfirmOpen(true)}
                className='bg-red-600/20 border border-red-500/30 text-red-400 hover:bg-red-500/30 hover:text-white'
              >
                <ImageIcon className='w-4 h-4 mr-2' />
                Delete All Images
              </Button>
              <Button
                type='button'
                variant='destructive'
                size='sm'
                onClick={() => setDeleteAllTimelapsesConfirmOpen(true)}
                className='bg-red-600/20 border border-red-500/30 text-red-400 hover:bg-red-500/30 hover:text-white'
              >
                <Trash2 className='w-4 h-4 mr-2' />
                Delete All Timelapses
              </Button>
              <Button
                type='button'
                variant='destructive'
                size='sm'
                onClick={() => setDeleteAllThumbnailsConfirmOpen(true)}
                className='bg-red-600/20 border border-red-500/30 text-red-400 hover:bg-red-500/30 hover:text-white'
              >
                <ImageIcon className='w-4 h-4 mr-2' />
                Delete All Thumbnails
              </Button>
            </div>
          </CardContent>
        </Card>
      </form>

      {/* Current Configuration - Full Width */}
      <Card className='transition-all duration-300 glass hover:glow'>
        <CardHeader>
          <CardTitle className='flex items-center space-x-2'>
            <SettingsIcon className='w-5 h-5 text-primary' />
            <span>Current Configuration</span>
          </CardTitle>
          <CardDescription>
            Active system settings and their values
          </CardDescription>
        </CardHeader>
        <CardContent className='space-y-4'>
          <div className='grid gap-4 md:grid-cols-2 lg:grid-cols-3'>
            {[
              { key: "capture_interval", value: captureInterval, displayValue: captureInterval.toString() },
              { key: "timezone", value: timezone, displayValue: timezone },
              { key: "generate_thumbnails", value: generateThumbnails, displayValue: generateThumbnails.toString() },
              { key: "image_capture_type", value: imageCaptureType, displayValue: imageCaptureType },
              { key: "log_retention_days", value: logRetentionDays, displayValue: logRetentionDays.toString() },
              { key: "max_log_file_size", value: maxLogFileSize, displayValue: maxLogFileSize.toString() },
              { key: "log_level", value: logLevel, displayValue: logLevel },
            ].map(({ key, value, displayValue }) => (
              <div
                key={key}
                className='flex items-center justify-between p-3 border rounded-lg bg-background/50 border-borderColor/50'
              >
                <div className='space-y-1'>
                  <p className='text-sm font-medium capitalize'>
                    {key.replace(/_/g, " ")}
                  </p>
                  {key === "capture_interval" && (
                    <p className='text-xs text-muted-foreground'>
                      {getIntervalPreset(value as number)}
                    </p>
                  )}
                  {key === "timezone" && (
                    <p className='text-xs text-muted-foreground'>
                      {new Date().toLocaleString("en-US", {
                        timeZone: displayValue,
                        hour: "2-digit",
                        minute: "2-digit",
                        hour12: true,
                      })}
                    </p>
                  )}
                </div>
                <Badge variant='secondary'>
                  {key === "capture_interval"
                    ? formatInterval(value as number)
                    : key === "timezone"
                    ? displayValue.split("/").pop()
                    : displayValue}
                </Badge>
              </div>
            ))}
          </div>

          {Object.keys(settings).length === 0 && (
            <div className='py-6 text-center'>
              <p className='text-sm text-muted-foreground'>
                No settings configured yet
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Info Cards */}
      <div className='grid gap-6 md:grid-cols-2'>
        <Card className='glass border-borderColor/50'>
          <CardHeader>
            <CardTitle className='text-lg'>💡 Capture Guidelines</CardTitle>
          </CardHeader>
          <CardContent className='space-y-3 text-sm text-muted-foreground'>
            <div className='space-y-2'>
              <p>
                <strong className='text-foreground'>
                  Fast intervals (1-30s):
                </strong>{" "}
                High-detail timelapses, short events
              </p>
              <p>
                <strong className='text-foreground'>
                  Medium intervals (1-15m):
                </strong>{" "}
                Construction, daily activities
              </p>
              <p>
                <strong className='text-foreground'>
                  Slow intervals (1-6h):
                </strong>{" "}
                Long-term projects, seasonal changes
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className='glass border-borderColor/50'>
          <CardHeader>
            <CardTitle className='text-lg'>⚙️ System Info</CardTitle>
          </CardHeader>
          <CardContent className='space-y-3 text-sm text-muted-foreground'>
            <div className='space-y-2'>
              <p>
                <strong className='text-foreground'>Time Windows:</strong>{" "}
                Configure per-camera to capture only during specific hours
              </p>
              <p>
                <strong className='text-foreground'>Health Monitoring:</strong>{" "}
                Cameras automatically marked offline after failures
              </p>
              <p>
                <strong className='text-foreground'>Auto-Cleanup:</strong> Old
                images and logs are automatically managed
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Thumbnail Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={thumbnailConfirmOpen}
        onClose={() => setThumbnailConfirmOpen(false)}
        onConfirm={() => {
          setThumbnailConfirmOpen(false)
          setThumbnailModalOpen(true)
        }}
        title='Regenerate All Thumbnails'
        description='Are you sure? This might take a while to process all existing images and generate thumbnails.'
        confirmLabel='Yes, Start Regeneration'
        cancelLabel='Cancel'
        variant='warning'
        icon={<ImageIcon className='w-6 h-6' />}
      />

      {/* Thumbnail Regeneration Modal */}
      <ThumbnailRegenerationModal
        isOpen={thumbnailModalOpen}
        onClose={() => setThumbnailModalOpen(false)}
      />

      {/* Image Format Change Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={imageFormatChangeDialogOpen}
        onClose={handleImageFormatCancel}
        onConfirm={handleImageFormatConfirm}
        title='Change Image Capture Type'
        description='This change will only impact future image captures. Do you want to convert existing image captures now? This may take awhile.'
        confirmLabel='Yes, Convert Existing Images'
        cancelLabel='No, Only Future Captures'
        variant='warning'
        icon={<ImageIcon className='w-6 h-6' />}
      />

      {/* Image Conversion Progress Modal - TODO: Make ThumbnailRegenerationModal reusable */}
      <ThumbnailRegenerationModal
        isOpen={imageConversionDialogOpen}
        onClose={() => setImageConversionDialogOpen(false)}
      />

      {/* Clean Logs Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={cleanLogsConfirmOpen}
        onClose={() => setCleanLogsConfirmOpen(false)}
        onConfirm={handleCleanLogsNow}
        title='Clean System Logs'
        description='Are you sure you want to delete all system log files? This action cannot be undone.'
        confirmLabel='Yes, Clean Logs'
        cancelLabel='Cancel'
        variant='warning'
        icon={<FileText className='w-6 h-6' />}
      />

      {/* Reset System Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={resetSystemConfirmOpen}
        onClose={() => setResetSystemConfirmOpen(false)}
        onConfirm={handleResetSystem}
        title='Reset Whole System'
        description='This will delete ALL data including cameras, timelapses, images, and settings. This action CANNOT be undone!'
        confirmLabel='Yes, Reset Everything'
        cancelLabel='Cancel'
        variant='danger'
        icon={<RotateCcw className='w-6 h-6' />}
      />

      {/* Delete All Cameras Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={deleteAllCamerasConfirmOpen}
        onClose={() => setDeleteAllCamerasConfirmOpen(false)}
        onConfirm={handleDeleteAllCameras}
        title='Delete All Cameras'
        description='This will permanently delete all camera configurations and their associated data. This action cannot be undone!'
        confirmLabel='Yes, Delete All Cameras'
        cancelLabel='Cancel'
        variant='danger'
        icon={<Trash2 className='w-6 h-6' />}
      />

      {/* Delete All Images Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={deleteAllImagesConfirmOpen}
        onClose={() => setDeleteAllImagesConfirmOpen(false)}
        onConfirm={handleDeleteAllImages}
        title='Delete All Image Captures'
        description='This will permanently delete all captured images from all cameras and timelapses. This action cannot be undone!'
        confirmLabel='Yes, Delete All Images'
        cancelLabel='Cancel'
        variant='danger'
        icon={<ImageIcon className='w-6 h-6' />}
      />

      {/* Delete All Timelapses Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={deleteAllTimelapsesConfirmOpen}
        onClose={() => setDeleteAllTimelapsesConfirmOpen(false)}
        onConfirm={handleDeleteAllTimelapses}
        title='Delete All Timelapses'
        description='This will permanently delete all timelapse configurations and their associated data. This action cannot be undone!'
        confirmLabel='Yes, Delete All Timelapses'
        cancelLabel='Cancel'
        variant='danger'
        icon={<Trash2 className='w-6 h-6' />}
      />

      {/* Reset Settings Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={resetSettingsConfirmOpen}
        onClose={() => setResetSettingsConfirmOpen(false)}
        onConfirm={handleResetSettings}
        title='Reset All Settings'
        description='This will reset all application settings to their default values. This action cannot be undone!'
        confirmLabel='Yes, Reset Settings'
        cancelLabel='Cancel'
        variant='warning'
        icon={<RotateCcw className='w-6 h-6' />}
      />

      {/* Delete All Thumbnails Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={deleteAllThumbnailsConfirmOpen}
        onClose={() => setDeleteAllThumbnailsConfirmOpen(false)}
        onConfirm={handleDeleteAllThumbnails}
        title='Delete All Thumbnails'
        description='This will permanently delete all thumbnail images. Original captures will remain untouched. This action cannot be undone!'
        confirmLabel='Yes, Delete All Thumbnails'
        cancelLabel='Cancel'
        variant='warning'
        icon={<ImageIcon className='w-6 h-6' />}
      />
    </div>
  )
}
