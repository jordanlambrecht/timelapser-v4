// src/components/timelapse-creation/slides/video-automation-slide.tsx
"use client"

import { useState } from "react"
import { useAutoAnimate } from "@formkit/auto-animate/react"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ToggleGroup } from "@/components/ui/toggle-group"
import { MultiToggleGroup } from "@/components/ui/multi-toggle-group"
import { NumberInput } from "@/components/ui/number-input"
import { Button } from "@/components/ui/button"
import { SuperSwitch } from "@/components/ui/switch"
import { Video, Clock, Target, Calendar, Plus, Trash2, X } from "lucide-react"
import { cn } from "@/lib/utils"
import type { TimelapseForm } from "../timelapse-creation-modal"

interface VideoAutomationSlideProps {
  form: TimelapseForm
  updateForm: (updates: Partial<TimelapseForm>) => void
}

const MILESTONE_PRESETS = [
  { label: "Every 100", value: 100 },
  { label: "Every 250", value: 250 },
  { label: "Every 500", value: 500 },
  { label: "Every 1000", value: 1000 },
  { label: "Every 2500", value: 2500 },
]

const DAYS_OF_WEEK = [
  { label: "Sun", value: "0" },
  { label: "Mon", value: "1" },
  { label: "Tue", value: "2" },
  { label: "Wed", value: "3" },
  { label: "Thu", value: "4" },
  { label: "Fri", value: "5" },
  { label: "Sat", value: "6" }
]

export function VideoAutomationSlide({
  form,
  updateForm,
}: VideoAutomationSlideProps) {
  const [configRef] = useAutoAnimate({ duration: 250 })

  // Handle manual only toggle - uncheck other options when enabled
  const handleManualOnlyChange = (checked: boolean) => {
    if (checked) {
      updateForm({
        videoManualOnly: true,
        videoPerCapture: false,
        videoScheduled: false,
        videoMilestone: false,
      })
    } else {
      updateForm({ videoManualOnly: false })
    }
  }

  // Handle other generation methods - disable manual when any are enabled
  const handlePerCaptureChange = (checked: boolean) => {
    if (checked) {
      updateForm({
        videoManualOnly: false,
        videoPerCapture: true,
      })
    } else {
      updateForm({ videoPerCapture: false })
    }
  }

  const handleScheduledChange = (checked: boolean) => {
    if (checked) {
      updateForm({
        videoManualOnly: false,
        videoScheduled: true,
      })
    } else {
      updateForm({ videoScheduled: false })
    }
  }

  const handleMilestoneChange = (checked: boolean) => {
    if (checked) {
      updateForm({
        videoManualOnly: false,
        videoMilestone: true,
      })
    } else {
      updateForm({ videoMilestone: false })
    }
  }

  // Calculate generation frequency based on capture interval
  const calculateFrequency = (intervalImages: number) => {
    if (!form.captureInterval || intervalImages <= 0) return "N/A"
    
    const secondsPerVideo = intervalImages * form.captureInterval
    
    if (secondsPerVideo < 3600) {
      return `Every ${Math.round(secondsPerVideo / 60)} minutes`
    } else if (secondsPerVideo < 86400) {
      const hours = Math.round(secondsPerVideo / 3600 * 10) / 10
      return `Every ${hours} hours`
    } else {
      const days = Math.round(secondsPerVideo / 86400 * 10) / 10
      return `Every ${days} days`
    }
  }

  return (
    <div className="px-1 space-y-6">
      <div className="text-center">
        <h3 className="text-xl font-semibold text-white mb-2">Video Generation Automation</h3>
        <p className="text-grey-light/70">Configure when timelapse videos are automatically generated</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Options */}
        <div className="space-y-4">
          <Label className="text-white font-medium">Automation Options</Label>
          
          {/* Manual Only */}
          <label htmlFor="manual-only" className="flex items-center space-x-3 cursor-pointer">
            <Checkbox
              id="manual-only"
              checked={form.videoManualOnly}
              onCheckedChange={handleManualOnlyChange}
            />
            <div className="flex items-center space-x-2">
              <Video className="w-4 h-4 text-grey-light" />
              <div>
                <span className="text-white font-medium">
                  Manual Only
                </span>
                <p className="text-xs text-grey-light/60">Generate videos manually when needed</p>
              </div>
            </div>
          </label>

          {/* Per-Capture */}
          <label htmlFor="per-capture" className="flex items-center space-x-3 cursor-pointer">
            <Checkbox
              id="per-capture"
              checked={form.videoPerCapture}
              onCheckedChange={handlePerCaptureChange}
            />
            <div className="flex items-center space-x-2">
              <Target className="w-4 h-4 text-cyan" />
              <div>
                <span className="text-white font-medium">
                  Per-Capture Generation
                </span>
                <p className="text-xs text-grey-light/60">
                  Generate after each image (throttled, always overwrites)
                </p>
              </div>
            </div>
          </label>

          {/* Scheduled */}
          <label htmlFor="scheduled" className="flex items-center space-x-3 cursor-pointer">
            <Checkbox
              id="scheduled"
              checked={form.videoScheduled}
              onCheckedChange={handleScheduledChange}
            />
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-purple" />
              <div>
                <span className="text-white font-medium">
                  Scheduled Generation
                </span>
                <p className="text-xs text-grey-light/60">
                  Generate at specific times daily or weekly
                </p>
              </div>
            </div>
          </label>

          {/* Milestone */}
          <label htmlFor="milestone" className="flex items-center space-x-3 cursor-pointer">
            <Checkbox
              id="milestone"
              checked={form.videoMilestone}
              onCheckedChange={handleMilestoneChange}
            />
            <div className="flex items-center space-x-2">
              <Calendar className="w-4 h-4 text-green-400" />
              <div>
                <span className="text-white font-medium">
                  Milestone Generation
                </span>
                <p className="text-xs text-grey-light/60">
                  Generate every X images captured
                </p>
              </div>
            </div>
          </label>
        </div>

        {/* Right Column - Configuration */}
        <div ref={configRef} className="lg:col-span-2 space-y-3">
          <Label className="text-white font-medium">Configuration</Label>
          
          {/* Scheduled Configuration */}
          {form.videoScheduled && !form.videoManualOnly && (
            <div className="p-3 bg-purple/5 border border-purple/20 rounded-lg space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Clock className="w-4 h-4 text-purple" />
                  <Label className="text-purple font-medium">Scheduled Generation</Label>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => updateForm({ videoScheduled: false })}
                  className="h-6 w-6 p-0 text-purple/60 hover:text-purple hover:bg-purple/10"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
              
              <ToggleGroup
                options={[
                  { label: "Daily", value: "daily" },
                  { label: "Weekly", value: "weekly" }
                ]}
                value={form.videoScheduleType}
                onValueChange={(value) => updateForm({ videoScheduleType: value as "daily" | "weekly" })}
                label="Schedule Type"
                colorTheme="cyan"
                borderFaded={true}
              />
              
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-purple text-xs">Time</Label>
                  <Input
                    type="time"
                    value={form.videoScheduleTime}
                    onChange={(e) => updateForm({ videoScheduleTime: e.target.value })}
                    className="w-full bg-black/20 border-purple/30 text-white"
                  />
                </div>
                
                {form.videoScheduleType === "weekly" && (
                  <div className="col-span-2 space-y-1">
                    <Label className="text-purple text-xs">Days of Week</Label>
                    <MultiToggleGroup
                      options={DAYS_OF_WEEK}
                      values={form.videoScheduleDays?.map(day => day.toString()) || []}
                      onValueChange={(values) => updateForm({ videoScheduleDays: values.map(v => parseInt(v)) })}
                      label=""
                      colorTheme="cyan"
                      borderFaded={true}
                      orientation="horizontal"
                    />
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between">
                <Label className="text-purple text-sm">Overwrite Existing</Label>
                <SuperSwitch
                  checked={form.videoScheduleOverwrite}
                  onCheckedChange={(checked) => updateForm({ videoScheduleOverwrite: checked })}
                  colorTheme="cyan"
                />
              </div>
            </div>
          )}

          {/* Milestone Configuration */}
          {form.videoMilestone && !form.videoManualOnly && (
            <div className="p-3 bg-green-500/5 border border-green-500/20 rounded-lg space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Calendar className="w-4 h-4 text-green-400" />
                  <Label className="text-green-400 font-medium">Milestone Generation</Label>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => updateForm({ videoMilestone: false })}
                  className="h-6 w-6 p-0 text-green-400/60 hover:text-green-400 hover:bg-green-500/10"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
              
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-green-400 text-xs">Generate every X images</Label>
                  <NumberInput
                    value={form.videoMilestoneInterval}
                    onChange={(value) => updateForm({ videoMilestoneInterval: value })}
                    min={1}
                    max={10000}
                    variant="buttons"
                    hideLabel={true}
                    className="bg-black/20 border-green-500/30 text-white"
                  />
                </div>
                
                <div className="space-y-1">
                  <Label className="text-green-400 text-xs">Frequency</Label>
                  <div className="h-10 flex items-center px-3 bg-green-500/10 border border-green-500/30 rounded-lg">
                    <span className="text-white text-sm font-medium">
                      {calculateFrequency(form.videoMilestoneInterval)}
                    </span>
                  </div>
                </div>
                
                <div className="col-span-2 space-y-1">
                  <Label className="text-green-400 text-xs">Quick Presets</Label>
                  <div className="grid grid-cols-3 sm:grid-cols-5 gap-1">
                    {MILESTONE_PRESETS.map((preset) => (
                      <Button
                        key={preset.value}
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => updateForm({ videoMilestoneInterval: preset.value })}
                        className={cn(
                          "h-7 text-xs px-2 transition-all duration-300",
                          form.videoMilestoneInterval === preset.value
                            ? "bg-green-500/20 border-green-400 text-green-400 hover:bg-green-500/30"
                            : "bg-black/20 border-green-500/30 text-grey-light hover:bg-green-500/10 hover:border-green-500/50 hover:text-white"
                        )}
                      >
                        {preset.label.replace("Every ", "")}
                      </Button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <Label className="text-green-400 text-sm">Overwrite Existing</Label>
                <SuperSwitch
                  checked={form.videoMilestoneOverwrite}
                  onCheckedChange={(checked) => updateForm({ videoMilestoneOverwrite: checked })}
                  colorTheme="cyan"
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}