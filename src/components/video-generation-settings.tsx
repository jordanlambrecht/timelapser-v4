// src/components/video-generation-settings.tsx

"use client"

import { useState, useEffect } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"
import { Info, AlertTriangle, Clock, Zap } from "lucide-react"
import type {
  VideoGenerationSettings,
  VideoGenerationSettingsProps,
  CalculationPreview,
} from "@/types"

export function VideoGenerationSettings({
  settings,
  onChange,
  isInherited = false,
  onResetToDefaults,
  totalImages = 0,
  className = "",
  showPreview = true,
}: VideoGenerationSettingsProps) {
  const [localSettings, setLocalSettings] =
    useState<VideoGenerationSettings>(settings)
  const [preview, setPreview] = useState<CalculationPreview | null>(null)
  const [validationErrors, setValidationErrors] = useState<string[]>([])

  // Update local settings when props change
  useEffect(() => {
    setLocalSettings(settings)
  }, [settings])

  // Calculate preview when settings or totalImages change
  useEffect(() => {
    if (showPreview && totalImages > 0) {
      calculatePreview()
    }
  }, [localSettings, totalImages, showPreview])

  const updateSettings = (updates: Partial<VideoGenerationSettings>) => {
    const newSettings = { ...localSettings, ...updates }
    setLocalSettings(newSettings)
    onChange(newSettings)
  }

  const validateSettings = (
    settingsToValidate: VideoGenerationSettings
  ): string[] => {
    const errors: string[] = []

    if (
      settingsToValidate.standard_fps < 1 ||
      settingsToValidate.standard_fps > 120
    ) {
      errors.push("Standard FPS must be between 1 and 120")
    }

    if (
      settingsToValidate.fps_bounds_min < 1 ||
      settingsToValidate.fps_bounds_max > 120
    ) {
      errors.push("FPS bounds must be between 1 and 120")
    }

    if (
      settingsToValidate.fps_bounds_min >= settingsToValidate.fps_bounds_max
    ) {
      errors.push("Minimum FPS bound must be less than maximum FPS bound")
    }

    if (
      settingsToValidate.enable_time_limits &&
      settingsToValidate.min_time_seconds &&
      settingsToValidate.max_time_seconds &&
      settingsToValidate.min_time_seconds >= settingsToValidate.max_time_seconds
    ) {
      errors.push("Minimum time must be less than maximum time")
    }

    if (
      settingsToValidate.video_generation_mode === "target" &&
      (!settingsToValidate.target_time_seconds ||
        settingsToValidate.target_time_seconds < 1)
    ) {
      errors.push("Target time must be specified and positive for target mode")
    }

    return errors
  }

  const calculatePreview = () => {
    if (totalImages < 10) {
      setPreview({
        estimated_fps: 0,
        estimated_duration: 0,
        duration_formatted: "0:00",
        fps_was_adjusted: false,
        error: `Not enough images for video generation (have ${totalImages}, need at least 10)`,
      })
      return
    }

    const errors = validateSettings(localSettings)
    if (errors.length > 0) {
      setPreview({
        estimated_fps: 0,
        estimated_duration: 0,
        duration_formatted: "0:00",
        fps_was_adjusted: false,
        error: errors[0],
      })
      return
    }

    let fps = localSettings.standard_fps
    let fps_was_adjusted = false
    let adjustment_reason = ""

    if (localSettings.video_generation_mode === "standard") {
      const estimated_duration = totalImages / localSettings.standard_fps

      if (localSettings.enable_time_limits) {
        if (
          localSettings.min_time_seconds &&
          estimated_duration < localSettings.min_time_seconds
        ) {
          fps = totalImages / localSettings.min_time_seconds
          fps_was_adjusted = true
          adjustment_reason = `Adjusted from ${localSettings.standard_fps} FPS to meet ${localSettings.min_time_seconds}s minimum`
        } else if (
          localSettings.max_time_seconds &&
          estimated_duration > localSettings.max_time_seconds
        ) {
          fps = totalImages / localSettings.max_time_seconds
          fps_was_adjusted = true
          adjustment_reason = `Adjusted from ${localSettings.standard_fps} FPS to meet ${localSettings.max_time_seconds}s maximum`
        }
      }
    } else if (
      localSettings.video_generation_mode === "target" &&
      localSettings.target_time_seconds
    ) {
      const required_fps = totalImages / localSettings.target_time_seconds

      if (required_fps < localSettings.fps_bounds_min) {
        fps = localSettings.fps_bounds_min
        fps_was_adjusted = true
        adjustment_reason = `FPS clamped to minimum bound (${localSettings.fps_bounds_min})`
      } else if (required_fps > localSettings.fps_bounds_max) {
        fps = localSettings.fps_bounds_max
        fps_was_adjusted = true
        adjustment_reason = `FPS clamped to maximum bound (${localSettings.fps_bounds_max})`
      } else {
        fps = required_fps
      }
    }

    const final_duration = totalImages / fps
    const minutes = Math.floor(final_duration / 60)
    const seconds = Math.floor(final_duration % 60)

    setPreview({
      estimated_fps: fps,
      estimated_duration: final_duration,
      duration_formatted: `${minutes}:${seconds.toString().padStart(2, "0")}`,
      fps_was_adjusted,
      adjustment_reason,
    })
  }

  // Validate current settings
  useEffect(() => {
    const errors = validateSettings(localSettings)
    setValidationErrors(errors)
  }, [localSettings])

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className='flex items-center gap-2'>
          <Zap className='h-5 w-5' />
          Video Generation Settings
          {isInherited && (
            <Badge variant='outline' className='text-xs'>
              Inherited
            </Badge>
          )}
        </CardTitle>
        <CardDescription>
          Configure how timelapses are converted to videos
        </CardDescription>
        {onResetToDefaults && (
          <Button variant='outline' size='sm' onClick={onResetToDefaults}>
            Reset to Camera Defaults
          </Button>
        )}
      </CardHeader>
      <CardContent className='space-y-6'>
        {/* Generation Mode Selection */}
        <div className='space-y-3'>
          <Label className='text-base font-medium'>Video Generation Mode</Label>
          <RadioGroup
            value={localSettings.video_generation_mode}
            onValueChange={(value: "standard" | "target") =>
              updateSettings({ video_generation_mode: value })
            }
          >
            <div className='flex items-center space-x-2'>
              <RadioGroupItem value='standard' id='standard' />
              <Label htmlFor='standard' className='flex items-center gap-2'>
                <Clock className='h-4 w-4' />
                Standard FPS Mode
              </Label>
            </div>
            <div className='flex items-center space-x-2'>
              <RadioGroupItem value='target' id='target' />
              <Label htmlFor='target' className='flex items-center gap-2'>
                <Zap className='h-4 w-4' />
                Target Time Mode
              </Label>
            </div>
          </RadioGroup>
        </div>

        <Separator />

        {/* Standard FPS Mode Settings */}
        {localSettings.video_generation_mode === "standard" && (
          <div className='space-y-4'>
            <div className='space-y-2'>
              <Label htmlFor='standard_fps'>Standard FPS</Label>
              <Input
                id='standard_fps'
                type='number'
                min='1'
                max='120'
                value={localSettings.standard_fps}
                onChange={(e) =>
                  updateSettings({
                    standard_fps: parseInt(e.target.value) || 12,
                  })
                }
              />
              <p className='text-sm text-muted-foreground'>
                Frames per second for video generation (1-120)
              </p>
            </div>

            <div className='space-y-3'>
              <div className='flex items-center space-x-2'>
                <Checkbox
                  id='enable_time_limits'
                  checked={localSettings.enable_time_limits}
                  onCheckedChange={(checked) =>
                    updateSettings({ enable_time_limits: !!checked })
                  }
                />
                <Label htmlFor='enable_time_limits'>Enable time limits</Label>
              </div>

              {localSettings.enable_time_limits && (
                <div className='grid grid-cols-2 gap-4 ml-6'>
                  <div className='space-y-2'>
                    <div className='flex items-center space-x-2'>
                      <Checkbox
                        id='enable_min_time'
                        checked={localSettings.min_time_seconds !== null}
                        onCheckedChange={(checked) =>
                          updateSettings({
                            min_time_seconds: checked ? 30 : null,
                          })
                        }
                      />
                      <Label htmlFor='enable_min_time'>
                        Min time (seconds)
                      </Label>
                    </div>
                    {localSettings.min_time_seconds !== null && (
                      <Input
                        type='number'
                        min='1'
                        max='3600'
                        value={localSettings.min_time_seconds || ""}
                        onChange={(e) =>
                          updateSettings({
                            min_time_seconds: parseInt(e.target.value) || null,
                          })
                        }
                      />
                    )}
                  </div>

                  <div className='space-y-2'>
                    <div className='flex items-center space-x-2'>
                      <Checkbox
                        id='enable_max_time'
                        checked={localSettings.max_time_seconds !== null}
                        onCheckedChange={(checked) =>
                          updateSettings({
                            max_time_seconds: checked ? 300 : null,
                          })
                        }
                      />
                      <Label htmlFor='enable_max_time'>
                        Max time (seconds)
                      </Label>
                    </div>
                    {localSettings.max_time_seconds !== null && (
                      <Input
                        type='number'
                        min='1'
                        max='3600'
                        value={localSettings.max_time_seconds || ""}
                        onChange={(e) =>
                          updateSettings({
                            max_time_seconds: parseInt(e.target.value) || null,
                          })
                        }
                      />
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Target Time Mode Settings */}
        {localSettings.video_generation_mode === "target" && (
          <div className='space-y-4'>
            <div className='space-y-2'>
              <Label htmlFor='target_time'>Target Duration (seconds)</Label>
              <Input
                id='target_time'
                type='number'
                min='1'
                max='3600'
                value={localSettings.target_time_seconds || ""}
                onChange={(e) =>
                  updateSettings({
                    target_time_seconds: parseInt(e.target.value) || null,
                  })
                }
              />
              <p className='text-sm text-muted-foreground'>
                Exact duration you want the final video to be
              </p>
            </div>

            <div className='grid grid-cols-2 gap-4'>
              <div className='space-y-2'>
                <Label htmlFor='fps_min'>Min FPS Bound</Label>
                <Input
                  id='fps_min'
                  type='number'
                  min='1'
                  max='60'
                  value={localSettings.fps_bounds_min}
                  onChange={(e) =>
                    updateSettings({
                      fps_bounds_min: parseInt(e.target.value) || 1,
                    })
                  }
                />
              </div>
              <div className='space-y-2'>
                <Label htmlFor='fps_max'>Max FPS Bound</Label>
                <Input
                  id='fps_max'
                  type='number'
                  min='1'
                  max='120'
                  value={localSettings.fps_bounds_max}
                  onChange={(e) =>
                    updateSettings({
                      fps_bounds_max: parseInt(e.target.value) || 60,
                    })
                  }
                />
              </div>
            </div>
            <p className='text-sm text-muted-foreground'>
              FPS will be calculated to meet target time, but clamped within
              these bounds
            </p>
          </div>
        )}

        {/* Validation Errors */}
        {validationErrors.length > 0 && (
          <Alert variant='destructive'>
            <AlertTriangle className='h-4 w-4' />
            <AlertDescription>
              <ul className='list-disc list-inside space-y-1'>
                {validationErrors.map((error, index) => (
                  <li key={index}>{error}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}

        {/* Preview Calculation */}
        {showPreview && (
          <>
            <Separator />
            <div className='space-y-3'>
              <Label className='text-base font-medium flex items-center gap-2'>
                <Info className='h-4 w-4' />
                Generation Preview
              </Label>

              {preview?.error ? (
                <Alert variant='destructive'>
                  <AlertTriangle className='h-4 w-4' />
                  <AlertDescription>{preview.error}</AlertDescription>
                </Alert>
              ) : preview ? (
                <div className='bg-muted/50 p-4 rounded-lg space-y-2'>
                  <div className='grid grid-cols-2 gap-4 text-sm'>
                    <div>
                      <strong>Total Images:</strong>{" "}
                      {totalImages.toLocaleString()}
                    </div>
                    <div>
                      <strong>Calculated FPS:</strong>{" "}
                      {preview.estimated_fps.toFixed(2)}
                    </div>
                    <div>
                      <strong>Video Duration:</strong>{" "}
                      {preview.duration_formatted}
                    </div>
                    <div>
                      <strong>Settings:</strong>{" "}
                      {localSettings.video_generation_mode} mode
                    </div>
                  </div>

                  {preview.fps_was_adjusted && preview.adjustment_reason && (
                    <Alert>
                      <Info className='h-4 w-4' />
                      <AlertDescription>
                        <strong>Auto-adjustment:</strong>{" "}
                        {preview.adjustment_reason}
                      </AlertDescription>
                    </Alert>
                  )}
                </div>
              ) : (
                <p className='text-sm text-muted-foreground'>
                  Add images to see preview calculation
                </p>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
