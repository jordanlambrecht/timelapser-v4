// src/components/new-timelapse-dialog.tsx
"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { NumberInput } from "@/components/ui/number-input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Calendar, Clock, Play, Settings, Sunrise, Sunset } from "lucide-react"
import { toast } from "@/lib/toast"
import { CreateTimelapseDialogProps, TimelapseConfig } from "@types"

export function CreateTimelapseDialog({
  isOpen,
  onClose,
  onConfirm,
  cameraId,
  cameraName,
  defaultTimeWindow,
}: CreateTimelapseDialogProps) {
  const [config, setConfig] = useState<TimelapseConfig>({
    name: "",
    timeWindowType: "none",
    timeWindowStart: defaultTimeWindow?.start || "06:00",
    timeWindowEnd: defaultTimeWindow?.end || "18:00",
    sunriseOffsetMinutes: 45,
    sunsetOffsetMinutes: -45,
    useAutoStop: false,
    autoStopAt: "",
  })
  const [loading, setLoading] = useState(false)

  // Generate default name when dialog opens
  useEffect(() => {
    if (isOpen) {
      const now = new Date()
      const dateStr = now.toISOString().slice(0, 10) // YYYY-MM-DD
      const timeStr = now.toTimeString().slice(0, 5).replace(":", "") // HHMM
      const defaultName = `${cameraName} - ${dateStr} ${timeStr}`

      setConfig((prev) => ({
        ...prev,
        name: defaultName,
        timeWindowType: defaultTimeWindow?.enabled ? "time" : "none",
        timeWindowStart: defaultTimeWindow?.start || "06:00",
        timeWindowEnd: defaultTimeWindow?.end || "18:00",
        useAutoStop: false,
        autoStopAt: "",
      }))
    }
  }, [isOpen, cameraName, defaultTimeWindow])

  // Set default auto-stop to 24 hours from now
  useEffect(() => {
    if (config.useAutoStop && !config.autoStopAt) {
      const tomorrow = new Date()
      tomorrow.setDate(tomorrow.getDate() + 1)
      const defaultAutoStop = tomorrow.toISOString().slice(0, 16) // YYYY-MM-DDTHH:MM
      setConfig((prev) => ({ ...prev, autoStopAt: defaultAutoStop }))
    }
  }, [config.useAutoStop, config.autoStopAt])

  const handleSubmit = async () => {
    if (!config.name.trim()) {
      toast.error("Please enter a timelapse name")
      return
    }

    if (config.useAutoStop && !config.autoStopAt) {
      toast.error("Please set an auto-stop date and time")
      return
    }

    if (config.useAutoStop && config.autoStopAt) {
      const autoStopDate = new Date(config.autoStopAt)
      const now = new Date()
      if (autoStopDate <= now) {
        toast.error("Auto-stop time must be in the future")
        return
      }
    }

    if (config.timeWindowType === "time") {
      const startTime = config.timeWindowStart
      const endTime = config.timeWindowEnd
      if (startTime >= endTime) {
        toast.error("Start time must be before end time")
        return
      }
    }

    setLoading(true)
    try {
      await onConfirm(config)
      onClose()
    } catch (error) {
      // Error handling is done by parent component
    } finally {
      setLoading(false)
    }
  }

  const handleClose = () => {
    if (!loading) {
      onClose()
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className='sm:max-w-[500px] glass-opaque border-purple-muted'>
        <DialogHeader>
          <DialogTitle className='flex items-center space-x-2 text-white'>
            <Play className='w-5 h-5 text-success' />
            <span>Start New Timelapse</span>
          </DialogTitle>
          <DialogDescription className='text-grey-light/70'>
            Configure your new timelapse recording for {cameraName}
          </DialogDescription>
        </DialogHeader>

        <div className='space-y-6 py-4'>
          {/* Timelapse Name */}
          <div className='space-y-2'>
            <Label htmlFor='name' className='text-white font-medium'>
              Timelapse Name
            </Label>
            <Input
              id='name'
              value={config.name}
              onChange={(e) =>
                setConfig((prev) => ({ ...prev, name: e.target.value }))
              }
              placeholder='Enter timelapse name...'
              className='bg-black/20 border-purple-muted/30 text-white placeholder:text-grey-light/50'
              disabled={loading}
            />
          </div>

          {/* Time Window Settings */}
          <div className='space-y-4'>
            <div className='flex items-center space-x-2'>
              <Clock className='w-4 h-4 text-cyan' />
              <Label className='text-white font-medium'>
                Time Window Control
              </Label>
            </div>

            <RadioGroup
              value={config.timeWindowType}
              onValueChange={(value: "none" | "time" | "sunrise_sunset") =>
                setConfig((prev) => ({ ...prev, timeWindowType: value }))
              }
              className='space-y-3'
              disabled={loading}
            >
              <div className='flex items-center space-x-2'>
                <RadioGroupItem value='none' id='none' />
                <Label htmlFor='none' className='text-white'>
                  No time restrictions (capture 24/7)
                </Label>
              </div>

              <div className='flex items-center space-x-2'>
                <RadioGroupItem value='time' id='time' />
                <Label htmlFor='time' className='text-white'>
                  Fixed time window
                </Label>
              </div>

              <div className='flex items-center space-x-2'>
                <RadioGroupItem value='sunrise_sunset' id='sunrise_sunset' />
                <Label htmlFor='sunrise_sunset' className='text-white'>
                  Sunrise/sunset window
                </Label>
              </div>
            </RadioGroup>

            {/* Fixed Time Window Controls */}
            {config.timeWindowType === "time" && (
              <div className='ml-6 space-y-4 p-4 bg-cyan/5 border border-cyan/20 rounded-lg'>
                <div className='grid grid-cols-2 gap-4'>
                  <div className='space-y-2'>
                    <Label className='text-cyan text-sm'>Start Time</Label>
                    <Input
                      type='time'
                      value={config.timeWindowStart}
                      onChange={(e) =>
                        setConfig((prev) => ({
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
                      value={config.timeWindowEnd}
                      onChange={(e) =>
                        setConfig((prev) => ({
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
                  Recording will only occur during this time window each day
                </p>
              </div>
            )}

            {/* Sunrise/Sunset Window Controls */}
            {config.timeWindowType === "sunrise_sunset" && (
              <div className='ml-6 space-y-4 p-4 bg-yellow-500/5 border border-yellow-500/20 rounded-lg'>
                <div className='grid grid-cols-2 gap-4'>
                  <div className='space-y-2'>
                    <div className='flex items-center space-x-2'>
                      <Sunrise className='w-4 h-4 text-yellow-400' />
                      <Label className='text-yellow-400 text-sm'>
                        Sunrise Offset
                      </Label>
                    </div>
                    <div className='flex items-center space-x-2'>
                      <Button
                        type='button'
                        size='sm'
                        variant='outline'
                        onClick={() =>
                          setConfig((prev) => ({
                            ...prev,
                            sunriseOffsetMinutes:
                              prev.sunriseOffsetMinutes - 15,
                          }))
                        }
                        className='h-8 w-8 p-0 border-yellow-500/30 text-yellow-400'
                        disabled={loading}
                      >
                        -
                      </Button>
                      <NumberInput
                        step={15}
                        value={config.sunriseOffsetMinutes}
                        onChange={(value) =>
                          setConfig((prev) => ({
                            ...prev,
                            sunriseOffsetMinutes: value,
                          }))
                        }
                        className='text-center bg-black/20 border-yellow-500/30 text-white'
                        disabled={loading}
                      />
                      <Button
                        type='button'
                        size='sm'
                        variant='outline'
                        onClick={() =>
                          setConfig((prev) => ({
                            ...prev,
                            sunriseOffsetMinutes:
                              prev.sunriseOffsetMinutes + 15,
                          }))
                        }
                        className='h-8 w-8 p-0 border-yellow-500/30 text-yellow-400'
                        disabled={loading}
                      >
                        +
                      </Button>
                    </div>
                    <p className='text-xs text-yellow-400/70'>
                      Minutes before (-) or after (+) sunrise
                    </p>
                  </div>

                  <div className='space-y-2'>
                    <div className='flex items-center space-x-2'>
                      <Sunset className='w-4 h-4 text-orange-400' />
                      <Label className='text-orange-400 text-sm'>
                        Sunset Offset
                      </Label>
                    </div>
                    <div className='flex items-center space-x-2'>
                      <Button
                        type='button'
                        size='sm'
                        variant='outline'
                        onClick={() =>
                          setConfig((prev) => ({
                            ...prev,
                            sunsetOffsetMinutes: prev.sunsetOffsetMinutes - 15,
                          }))
                        }
                        className='h-8 w-8 p-0 border-orange-500/30 text-orange-400'
                        disabled={loading}
                      >
                        -
                      </Button>
                      <NumberInput
                        step={15}
                        value={config.sunsetOffsetMinutes}
                        onChange={(value) =>
                          setConfig((prev) => ({
                            ...prev,
                            sunsetOffsetMinutes: value,
                          }))
                        }
                        className='text-center bg-black/20 border-orange-500/30 text-white'
                        disabled={loading}
                      />
                      <Button
                        type='button'
                        size='sm'
                        variant='outline'
                        onClick={() =>
                          setConfig((prev) => ({
                            ...prev,
                            sunsetOffsetMinutes: prev.sunsetOffsetMinutes + 15,
                          }))
                        }
                        className='h-8 w-8 p-0 border-orange-500/30 text-orange-400'
                        disabled={loading}
                      >
                        +
                      </Button>
                    </div>
                    <p className='text-xs text-orange-400/70'>
                      Minutes before (-) or after (+) sunset
                    </p>
                  </div>
                </div>
                <p className='text-xs text-yellow-500/70'>
                  Recording will occur from sunrise offset to sunset offset each
                  day
                </p>
              </div>
            )}
          </div>

          {/* Auto-Stop Settings */}
          <div className='space-y-4'>
            <div className='flex items-center space-x-3'>
              <Switch
                id='useAutoStop'
                checked={config.useAutoStop}
                onCheckedChange={(checked) =>
                  setConfig((prev) => ({ ...prev, useAutoStop: checked }))
                }
                disabled={loading}
              />
              <div className='flex items-center space-x-2'>
                <Calendar className='w-4 h-4 text-purple' />
                <Label htmlFor='useAutoStop' className='text-white font-medium'>
                  Auto-Stop Recording
                </Label>
              </div>
            </div>

            {config.useAutoStop && (
              <div className='ml-7 space-y-4 p-4 bg-purple/5 border border-purple/20 rounded-lg'>
                <div className='space-y-2'>
                  <Label className='text-purple text-sm'>
                    Stop Date & Time
                  </Label>
                  <Input
                    type='datetime-local'
                    value={config.autoStopAt}
                    onChange={(e) =>
                      setConfig((prev) => ({
                        ...prev,
                        autoStopAt: e.target.value,
                      }))
                    }
                    className='bg-black/20 border-purple/30 text-white'
                    disabled={loading}
                  />
                </div>
                <p className='text-xs text-purple/70'>
                  The timelapse will automatically stop at this date and time
                </p>
              </div>
            )}
          </div>
        </div>

        <DialogFooter className='space-x-3'>
          <Button
            variant='outline'
            onClick={handleClose}
            disabled={loading}
            className='border-grey-light/20 text-grey-light hover:bg-grey-light/10'
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={loading}
            className='bg-gradient-to-r from-pink to-cyan hover:from-pink-dark hover:to-cyan text-black font-medium'
          >
            {loading ? (
              <>
                <div className='w-4 h-4 mr-2 border-2 border-black/20 border-t-black rounded-full animate-spin' />
                Starting...
              </>
            ) : (
              <>
                <Play className='w-4 h-4 mr-2' />
                Start Timelapse
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
