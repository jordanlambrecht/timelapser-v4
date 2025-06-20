// src/components/ui/timelapse-settings-modal.tsx
"use client"

import { useState, useEffect } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { VideoGenerationSettings } from "@/components/video-generation-settings"
import {
  Settings,
  Clock,
  Calendar,
  Video,
  Save,
  RotateCcw,
  AlertTriangle,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "@/lib/toast"

interface TimelapseSettingsModalProps {
  isOpen: boolean
  onClose: () => void
  cameraId: number
  cameraName: string
  timelapseId?: number
  timelapseData?: any
  onSettingsUpdate?: () => void
}

interface TimelapseSettings {
  // Time window controls
  useCustomTimeWindow: boolean
  timeWindowStart: string
  timeWindowEnd: string

  // Auto-stop functionality
  useAutoStop: boolean
  autoStopAt?: string

  // Video generation settings
  videoSettings: any
}

export function TimelapseSettingsModal({
  isOpen,
  onClose,
  cameraId,
  cameraName,
  timelapseId,
  timelapseData,
  onSettingsUpdate,
}: TimelapseSettingsModalProps) {
  const [settings, setSettings] = useState<TimelapseSettings>({
    useCustomTimeWindow: false,
    timeWindowStart: "06:00",
    timeWindowEnd: "18:00",
    useAutoStop: false,
    autoStopAt: "",
    videoSettings: {},
  })
  const [loading, setLoading] = useState(false)
  const [originalSettings, setOriginalSettings] =
    useState<TimelapseSettings | null>(null)
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)

  // Load current settings when modal opens
  useEffect(() => {
    if (isOpen && timelapseId) {
      loadTimelapseSettings()
    } else if (isOpen && !timelapseId) {
      loadCameraDefaults()
    }
  }, [isOpen, timelapseId, cameraId])

  // Track unsaved changes
  useEffect(() => {
    if (originalSettings) {
      const hasChanges =
        JSON.stringify(settings) !== JSON.stringify(originalSettings)
      setHasUnsavedChanges(hasChanges)
    }
  }, [settings, originalSettings])

  const loadTimelapseSettings = async () => {
    if (!timelapseId) return

    try {
      setLoading(true)

      // Load timelapse-specific settings
      const [timelapseResponse, videoSettingsResponse] = await Promise.all([
        fetch(`/api/timelapses/${timelapseId}`),
        fetch(`/api/timelapses/${timelapseId}/video-settings`),
      ])

      if (timelapseResponse.ok && videoSettingsResponse.ok) {
        const timelapseData = await timelapseResponse.json()
        const videoSettings = await videoSettingsResponse.json()

        const loadedSettings: TimelapseSettings = {
          useCustomTimeWindow: timelapseData.use_custom_time_window || false,
          timeWindowStart: timelapseData.time_window_start || "06:00",
          timeWindowEnd: timelapseData.time_window_end || "18:00",
          useAutoStop: !!timelapseData.auto_stop_at,
          autoStopAt: timelapseData.auto_stop_at
            ? new Date(timelapseData.auto_stop_at).toISOString().slice(0, 16)
            : "",
          videoSettings,
        }

        setSettings(loadedSettings)
        setOriginalSettings(loadedSettings)
      }
    } catch (error) {
      console.error("Error loading timelapse settings:", error)
      toast.error("Failed to load settings", {
        description: "Please try again",
        duration: 4000,
      })
    } finally {
      setLoading(false)
    }
  }

  const loadCameraDefaults = async () => {
    try {
      setLoading(true)

      // Load camera defaults for new timelapse settings
      const [cameraResponse, videoSettingsResponse] = await Promise.all([
        fetch(`/api/cameras/${cameraId}`),
        fetch(`/api/cameras/${cameraId}/video-settings`),
      ])

      if (cameraResponse.ok && videoSettingsResponse.ok) {
        const cameraData = await cameraResponse.json()
        const videoSettings = await videoSettingsResponse.json()

        const defaultSettings: TimelapseSettings = {
          useCustomTimeWindow: false,
          timeWindowStart: cameraData.time_window_start || "06:00",
          timeWindowEnd: cameraData.time_window_end || "18:00",
          useAutoStop: false,
          autoStopAt: "",
          videoSettings,
        }

        setSettings(defaultSettings)
        setOriginalSettings(defaultSettings)
      }
    } catch (error) {
      console.error("Error loading camera defaults:", error)
      toast.error("Failed to load camera defaults", {
        description: "Please try again",
        duration: 4000,
      })
    } finally {
      setLoading(false)
    }
  }

  const handleSaveSettings = async () => {
    // Validate auto-stop time if enabled
    if (settings.useAutoStop && settings.autoStopAt) {
      const autoStopDate = new Date(settings.autoStopAt)
      const now = new Date()
      if (autoStopDate <= now) {
        toast.error("Auto-stop time must be in the future")
        return
      }
    }

    // Validate time window if enabled
    if (settings.useCustomTimeWindow) {
      if (settings.timeWindowStart >= settings.timeWindowEnd) {
        toast.error("Start time must be before end time")
        return
      }
    }

    try {
      setLoading(true)

      if (timelapseId) {
        // Update timelapse settings
        const timelapseUpdate = {
          use_custom_time_window: settings.useCustomTimeWindow,
          time_window_start: settings.useCustomTimeWindow
            ? settings.timeWindowStart
            : null,
          time_window_end: settings.useCustomTimeWindow
            ? settings.timeWindowEnd
            : null,
          auto_stop_at:
            settings.useAutoStop && settings.autoStopAt
              ? new Date(settings.autoStopAt).toISOString()
              : null,
        }

        const [timelapseResponse, videoResponse] = await Promise.all([
          fetch(`/api/timelapses/${timelapseId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(timelapseUpdate),
          }),
          fetch(`/api/timelapses/${timelapseId}/video-settings`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(settings.videoSettings),
          }),
        ])

        if (!timelapseResponse.ok || !videoResponse.ok) {
          throw new Error("Failed to save timelapse settings")
        }

        toast.success("Settings saved successfully", {
          description: "Timelapse settings have been updated",
          duration: 4000,
        })
      } else {
        // Update camera default settings
        const cameraUpdate = {
          use_time_window: settings.useCustomTimeWindow,
          time_window_start: settings.useCustomTimeWindow
            ? settings.timeWindowStart
            : null,
          time_window_end: settings.useCustomTimeWindow
            ? settings.timeWindowEnd
            : null,
          ...settings.videoSettings,
        }

        const response = await fetch(`/api/cameras/${cameraId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(cameraUpdate),
        })

        if (!response.ok) {
          throw new Error("Failed to save camera settings")
        }

        toast.success("Settings saved successfully", {
          description: "Camera default settings have been updated",
          duration: 4000,
        })
      }

      setOriginalSettings(settings)
      setHasUnsavedChanges(false)
      onSettingsUpdate?.()
      onClose()
    } catch (error) {
      console.error("Error saving settings:", error)
      toast.error("Failed to save settings", {
        description:
          error instanceof Error ? error.message : "Please try again",
        duration: 6000,
      })
    } finally {
      setLoading(false)
    }
  }

  const handleResetToDefaults = () => {
    if (originalSettings) {
      setSettings(originalSettings)
      setHasUnsavedChanges(false)
    }
  }

  const handleClose = () => {
    if (hasUnsavedChanges) {
      if (
        confirm("You have unsaved changes. Are you sure you want to close?")
      ) {
        onClose()
      }
    } else {
      onClose()
    }
  }

  // Set default auto-stop to 24 hours from now when enabled
  useEffect(() => {
    if (settings.useAutoStop && !settings.autoStopAt) {
      const tomorrow = new Date()
      tomorrow.setDate(tomorrow.getDate() + 1)
      const defaultAutoStop = tomorrow.toISOString().slice(0, 16)
      setSettings((prev) => ({ ...prev, autoStopAt: defaultAutoStop }))
    }
  }, [settings.useAutoStop, settings.autoStopAt])

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className='glass-strong border-purple-muted/50 max-w-5xl max-h-[90vh] overflow-hidden'>
        <DialogHeader className='relative'>
          <div className='absolute -top-2 -right-2 w-16 h-16 bg-gradient-to-bl from-purple/10 to-transparent rounded-full' />
          <DialogTitle className='flex items-center space-x-3 text-xl'>
            <div className='p-2 bg-gradient-to-br from-purple/20 to-cyan/20 rounded-xl'>
              <Settings className='w-6 h-6 text-white' />
            </div>
            <div>
              <span className='text-white'>Timelapse Settings</span>
              <p className='text-sm text-grey-light/60 font-normal mt-1'>
                {cameraName}{" "}
                {timelapseId
                  ? `- Timelapse ${timelapseId}`
                  : "- Default Settings"}
              </p>
            </div>
          </DialogTitle>
        </DialogHeader>

        <div className='mt-6 space-y-6 max-h-[calc(90vh-200px)] overflow-auto'>
          {loading ? (
            <div className='flex items-center justify-center py-12'>
              <div className='text-center space-y-4'>
                <div className='w-12 h-12 border-4 border-purple/20 border-t-purple rounded-full animate-spin mx-auto' />
                <p className='text-grey-light/60'>Loading settings...</p>
              </div>
            </div>
          ) : (
            <>
              {/* Time Window Controls */}
              <div className='space-y-4'>
                <div className='flex items-center space-x-3'>
                  <Clock className='w-5 h-5 text-cyan' />
                  <h3 className='text-lg font-bold text-white'>
                    Time Window Control
                  </h3>
                </div>

                <div className='glass p-4 rounded-xl border border-purple-muted/20 space-y-4'>
                  <div className='flex items-center space-x-3'>
                    <Switch
                      id='useCustomTimeWindow'
                      checked={settings.useCustomTimeWindow}
                      onCheckedChange={(checked) =>
                        setSettings((prev) => ({
                          ...prev,
                          useCustomTimeWindow: checked,
                        }))
                      }
                      disabled={loading}
                    />
                    <Label
                      htmlFor='useCustomTimeWindow'
                      className='text-white font-medium'
                    >
                      Override camera time window for this timelapse
                    </Label>
                  </div>

                  {settings.useCustomTimeWindow && (
                    <div className='ml-7 space-y-4 p-4 bg-cyan/5 border border-cyan/20 rounded-lg'>
                      <div className='grid grid-cols-2 gap-4'>
                        <div className='space-y-2'>
                          <Label className='text-cyan text-sm'>
                            Start Time
                          </Label>
                          <Input
                            type='time'
                            value={settings.timeWindowStart}
                            onChange={(e) =>
                              setSettings((prev) => ({
                                ...prev,
                                timeWindowStart: e.target.value,
                              }))
                            }
                            className='bg-black/20 border-cyan/30 text-white'
                            disabled={loading}
                          />
                        </div>
                        <div className='space-y-2'>
                          <Label className='text-cyan text-sm'>End Time</Label>
                          <Input
                            type='time'
                            value={settings.timeWindowEnd}
                            onChange={(e) =>
                              setSettings((prev) => ({
                                ...prev,
                                timeWindowEnd: e.target.value,
                              }))
                            }
                            className='bg-black/20 border-cyan/30 text-white'
                            disabled={loading}
                          />
                        </div>
                      </div>
                      <p className='text-xs text-cyan/70'>
                        Captures will only occur during this time window each
                        day
                      </p>
                    </div>
                  )}
                </div>
              </div>

              <Separator className='border-purple-muted/20' />

              {/* Auto-Stop Controls */}
              <div className='space-y-4'>
                <div className='flex items-center space-x-3'>
                  <Calendar className='w-5 h-5 text-purple' />
                  <h3 className='text-lg font-bold text-white'>
                    Auto-Stop Control
                  </h3>
                </div>

                <div className='glass p-4 rounded-xl border border-purple-muted/20 space-y-4'>
                  <div className='flex items-center space-x-3'>
                    <Switch
                      id='useAutoStop'
                      checked={settings.useAutoStop}
                      onCheckedChange={(checked) =>
                        setSettings((prev) => ({
                          ...prev,
                          useAutoStop: checked,
                        }))
                      }
                      disabled={loading}
                    />
                    <Label
                      htmlFor='useAutoStop'
                      className='text-white font-medium'
                    >
                      Automatically stop recording at a specific date and time
                    </Label>
                  </div>

                  {settings.useAutoStop && (
                    <div className='ml-7 space-y-4 p-4 bg-purple/5 border border-purple/20 rounded-lg'>
                      <div className='space-y-2'>
                        <Label className='text-purple text-sm'>
                          Stop Date & Time
                        </Label>
                        <Input
                          type='datetime-local'
                          value={settings.autoStopAt}
                          onChange={(e) =>
                            setSettings((prev) => ({
                              ...prev,
                              autoStopAt: e.target.value,
                            }))
                          }
                          className='bg-black/20 border-purple/30 text-white'
                          disabled={loading}
                        />
                      </div>
                      <div className='flex items-start space-x-2 text-xs text-purple/70'>
                        <AlertTriangle className='w-4 h-4 text-purple/50 mt-0.5 flex-shrink-0' />
                        <p>
                          The timelapse will automatically stop at this date and
                          time. Make sure to set a future time.
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <Separator className='border-purple-muted/20' />

              {/* Video Generation Settings */}
              <div className='space-y-4'>
                <div className='flex items-center space-x-3'>
                  <Video className='w-5 h-5 text-pink' />
                  <h3 className='text-lg font-bold text-white'>
                    Video Generation Settings
                  </h3>
                </div>

                <div className='glass p-4 rounded-xl border border-purple-muted/20'>
                  <VideoGenerationSettings
                    settings={settings.videoSettings}
                    onChange={(newVideoSettings) =>
                      setSettings((prev) => ({
                        ...prev,
                        videoSettings: newVideoSettings,
                      }))
                    }
                    totalImages={timelapseData?.total_images || 0}
                    showPreview={true}
                    className='space-y-4'
                  />
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer Actions */}
        <div className='flex items-center justify-between pt-4 border-t border-purple-muted/20'>
          <div className='flex items-center space-x-2'>
            {hasUnsavedChanges && (
              <div className='flex items-center space-x-2 text-amber-light/80'>
                <AlertTriangle className='w-4 h-4' />
                <span className='text-sm'>You have unsaved changes</span>
              </div>
            )}
          </div>

          <div className='flex items-center space-x-3'>
            <Button
              variant='outline'
              onClick={handleResetToDefaults}
              disabled={loading || !hasUnsavedChanges}
              className='border-grey-light/20 text-grey-light hover:bg-grey-light/10'
            >
              <RotateCcw className='w-4 h-4 mr-2' />
              Reset
            </Button>

            <Button
              variant='outline'
              onClick={handleClose}
              disabled={loading}
              className='border-grey-light/20 text-grey-light hover:bg-grey-light/10'
            >
              Cancel
            </Button>

            <Button
              onClick={handleSaveSettings}
              disabled={loading || !hasUnsavedChanges}
              className={cn(
                "font-medium",
                hasUnsavedChanges
                  ? "bg-gradient-to-r from-pink to-cyan hover:from-pink-dark hover:to-cyan text-black"
                  : "bg-grey-light/20 text-grey-light/50 cursor-not-allowed"
              )}
            >
              {loading ? (
                <>
                  <div className='w-4 h-4 mr-2 border-2 border-black/20 border-t-black rounded-full animate-spin' />
                  Saving...
                </>
              ) : (
                <>
                  <Save className='w-4 h-4 mr-2' />
                  Save Settings
                </>
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
