// src/components/edit-timelapse-modal/settings-tab.tsx
"use client"

import { useState } from "react"
import { useAutoAnimate } from "@formkit/auto-animate/react"
import { Input } from "@/components/ui/input"
import { NumberInput } from "@/components/ui/number-input"
import { Label } from "@/components/ui/label"
import { ToggleGroup } from "@/components/ui/toggle-group"
import { SuperSwitch } from "@/components/ui/switch"
import { Checkbox } from "@/components/ui/checkbox"
import { Button } from "@/components/ui/button"
import { MultiToggleGroup } from "@/components/ui/multi-toggle-group"
import { 
  Settings, 
  Timer, 
  Video, 
  Clock, 
  Calendar,
  Sunrise,
  Sunset,
  Target,
  Zap,
  Info
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useSettings } from "@/contexts/settings-context"

interface SettingsTabProps {
  timelapse: {
    id: number
    name: string
    status: string
    image_count: number
    start_date: string
    last_capture_at?: string
  }
  cameraId: number
  cameraName: string
  onDataChange?: () => void
}

// Mock form data - in real implementation this would come from the timelapse data
const mockTimelapseSettings = {
  captureInterval: 300, // 5 minutes
  runWindowEnabled: false,
  runWindowType: "between" as "between" | "sunrise-sunset",
  timeWindowStart: "06:00",
  timeWindowEnd: "18:00",
  sunriseOffsetMinutes: 0,
  sunsetOffsetMinutes: 0,
  stopTimeEnabled: false,
  stopType: "datetime" as "datetime" | "daycount",
  stopDateTime: "",
  stopDayCount: 7,
  videoGenerationMode: "standard" as "standard" | "target",
  videoStandardFps: 30,
  videoEnableTimeLimits: false,
  videoMinDuration: 10,
  videoMaxDuration: 300,
  videoTargetDuration: 60,
  videoFpsMin: 15,
  videoFpsMax: 60,
  videoQuality: "medium" as "low" | "medium" | "high",
  videoManualOnly: true,
  videoPerCapture: false,
  videoScheduled: false,
  videoMilestone: false,
  videoScheduleType: "daily" as "daily" | "weekly",
  videoScheduleTime: "18:00",
  videoScheduleDays: [1, 2, 3, 4, 5] as number[],
  videoScheduleOverwrite: false,
  videoMilestoneInterval: 100,
  videoMilestoneOverwrite: false,
}

const VIDEO_QUALITIES = [
  { label: "Low", value: "low", desc: "720p, faster processing" },
  { label: "Medium", value: "medium", desc: "1080p, balanced quality" },
  { label: "High", value: "high", desc: "Original resolution, best quality" },
]

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

export function SettingsTab({
  timelapse,
  cameraId,
  cameraName,
  onDataChange,
}: SettingsTabProps) {
  const { sunriseSunsetEnabled } = useSettings()
  const [form, setForm] = useState(mockTimelapseSettings)
  
  // AutoAnimate refs
  const [runWindowRef] = useAutoAnimate({ duration: 250 })
  const [stopTimeRef] = useAutoAnimate({ duration: 250 })
  const [videoConfigRef] = useAutoAnimate({ duration: 250 })
  const [automationConfigRef] = useAutoAnimate({ duration: 250 })

  const updateForm = (updates: Partial<typeof form>) => {
    setForm(prev => ({ ...prev, ...updates }))
    onDataChange?.()
  }

  const getMinDateTime = () => {
    const now = new Date()
    now.setMinutes(now.getMinutes() + 5) // 5 minutes from now
    return now.toISOString().slice(0, 16)
  }

  return (
    <div className="space-y-8 max-w-4xl">
      <div className="text-center">
        <div className="flex items-center justify-center gap-2 mb-2">
          <Settings className="w-5 h-5 text-cyan" />
          <h3 className="text-xl font-semibold text-white">Timelapse Settings</h3>
        </div>
        <p className="text-grey-light/70">
          Configure capture intervals, video generation, and automation settings
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left Column */}
        <div className="space-y-6">
          {/* Capture Interval */}
          <div className="space-y-3">
            <div className="flex items-center space-x-2">
              <Timer className="w-4 h-4 text-cyan" />
              <Label className="text-white font-medium">Capture Interval</Label>
            </div>
            <div className="p-4 bg-cyan/5 border border-cyan/20 rounded-lg space-y-3">
              <div className="space-y-2">
                <Label className="text-cyan text-sm">Interval (seconds)</Label>
                <NumberInput
                  value={form.captureInterval}
                  onChange={(value) => updateForm({ captureInterval: value })}
                  min={1}
                  max={86400}
                  variant="buttons"
                  hideLabel={true}
                  className="bg-black/20 border-cyan/30 text-white"
                />
              </div>
              <div className="text-xs text-cyan/70">
                Currently: {Math.floor(form.captureInterval / 60)}m {form.captureInterval % 60}s
              </div>
            </div>
          </div>

          {/* Time Window */}
          <div ref={runWindowRef} className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Clock className="w-4 h-4 text-purple" />
                <Label className="text-white font-medium">Run Window</Label>
              </div>
              <SuperSwitch
                checked={form.runWindowEnabled}
                onCheckedChange={(checked) => updateForm({ runWindowEnabled: checked })}
                colorTheme="cyan"
              />
            </div>

            {form.runWindowEnabled && (
              <div className="p-4 bg-purple/5 border border-purple/20 rounded-lg space-y-4">
                <ToggleGroup
                  options={[
                    { label: "Between Times", value: "between" },
                    { 
                      label: "Sunrise/Sunset", 
                      value: "sunrise-sunset",
                      disabled: !sunriseSunsetEnabled
                    }
                  ]}
                  value={form.runWindowType}
                  onValueChange={(value) => updateForm({ runWindowType: value as "between" | "sunrise-sunset" })}
                  label="Window Type"
                  colorTheme="cyan"
                  borderFaded={true}
                />

                {form.runWindowType === "between" && (
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-2">
                      <Label className="text-purple text-sm">Start</Label>
                      <Input
                        type="time"
                        value={form.timeWindowStart}
                        onChange={(e) => updateForm({ timeWindowStart: e.target.value })}
                        className="bg-black/20 border-purple/30 text-white"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-purple text-sm">End</Label>
                      <Input
                        type="time"
                        value={form.timeWindowEnd}
                        onChange={(e) => updateForm({ timeWindowEnd: e.target.value })}
                        className="bg-black/20 border-purple/30 text-white"
                      />
                    </div>
                  </div>
                )}

                {form.runWindowType === "sunrise-sunset" && (
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-2">
                      <div className="flex items-center space-x-2">
                        <Sunrise className="w-4 h-4 text-yellow-400" />
                        <Label className="text-yellow-400 text-sm">Sunrise Offset</Label>
                      </div>
                      <NumberInput
                        value={form.sunriseOffsetMinutes}
                        onChange={(value) => updateForm({ sunriseOffsetMinutes: value })}
                        variant="buttons"
                        hideLabel={true}
                        className="bg-black/20 border-yellow-500/30 text-white"
                      />
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center space-x-2">
                        <Sunset className="w-4 h-4 text-orange-400" />
                        <Label className="text-orange-400 text-sm">Sunset Offset</Label>
                      </div>
                      <NumberInput
                        value={form.sunsetOffsetMinutes}
                        onChange={(value) => updateForm({ sunsetOffsetMinutes: value })}
                        variant="buttons"
                        hideLabel={true}
                        className="bg-black/20 border-orange-500/30 text-white"
                      />
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Auto-Stop */}
          <div ref={stopTimeRef} className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Calendar className="w-4 h-4 text-green-400" />
                <Label className="text-white font-medium">Auto-Stop Recording</Label>
              </div>
              <SuperSwitch
                checked={form.stopTimeEnabled}
                onCheckedChange={(checked) => updateForm({ stopTimeEnabled: checked })}
                colorTheme="cyan"
              />
            </div>

            {form.stopTimeEnabled && (
              <div className="p-4 bg-green-500/5 border border-green-500/20 rounded-lg space-y-4">
                <ToggleGroup
                  options={[
                    { label: "Date & Time", value: "datetime" },
                    { label: "Day Count", value: "daycount" }
                  ]}
                  value={form.stopType}
                  onValueChange={(value) => updateForm({ stopType: value as "datetime" | "daycount" })}
                  label="Stop Method"
                  colorTheme="cyan"
                  borderFaded={true}
                />

                {form.stopType === "datetime" && (
                  <div className="space-y-2">
                    <Label className="text-green-400 text-sm">Stop Date & Time</Label>
                    <Input
                      type="datetime-local"
                      value={form.stopDateTime}
                      min={getMinDateTime()}
                      onChange={(e) => updateForm({ stopDateTime: e.target.value })}
                      className="bg-black/20 border-green-500/30 text-white"
                    />
                  </div>
                )}

                {form.stopType === "daycount" && (
                  <div className="space-y-2">
                    <Label className="text-green-400 text-sm">Number of Days</Label>
                    <NumberInput
                      value={form.stopDayCount}
                      onChange={(value) => updateForm({ stopDayCount: value })}
                      min={1}
                      variant="buttons"
                      hideLabel={true}
                      className="bg-black/20 border-green-500/30 text-white"
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          {/* Video Generation */}
          <div className="space-y-3">
            <div className="flex items-center space-x-2">
              <Video className="w-4 h-4 text-cyan" />
              <Label className="text-white font-medium">Video Generation</Label>
            </div>
            
            <div ref={videoConfigRef} className="p-4 bg-cyan/5 border border-cyan/20 rounded-lg space-y-4">
              <ToggleGroup
                options={[
                  { label: "Standard FPS", value: "standard" },
                  { label: "Target Duration", value: "target" }
                ]}
                value={form.videoGenerationMode}
                onValueChange={(value) => updateForm({ videoGenerationMode: value as "standard" | "target" })}
                label="Generation Mode"
                colorTheme="cyan"
                borderFaded={true}
              />

              {form.videoGenerationMode === "standard" && (
                <div className="space-y-3">
                  <div className="space-y-2">
                    <Label className="text-cyan text-sm">Frames Per Second</Label>
                    <NumberInput
                      value={form.videoStandardFps}
                      onChange={(value) => updateForm({ videoStandardFps: value })}
                      min={1}
                      max={120}
                      variant="buttons"
                      hideLabel={true}
                      className="bg-black/20 border-cyan/30 text-white"
                    />
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <Label className="text-cyan text-sm">Time Limits</Label>
                    <SuperSwitch
                      checked={form.videoEnableTimeLimits}
                      onCheckedChange={(checked) => updateForm({ videoEnableTimeLimits: checked })}
                      colorTheme="cyan"
                    />
                  </div>

                  {form.videoEnableTimeLimits && (
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-2">
                        <Label className="text-cyan text-xs">Min (s)</Label>
                        <NumberInput
                          value={form.videoMinDuration}
                          onChange={(value) => updateForm({ videoMinDuration: value })}
                          min={1}
                          variant="buttons"
                          hideLabel={true}
                          className="bg-black/20 border-cyan/30 text-white"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-cyan text-xs">Max (s)</Label>
                        <NumberInput
                          value={form.videoMaxDuration}
                          onChange={(value) => updateForm({ videoMaxDuration: value })}
                          min={1}
                          variant="buttons"
                          hideLabel={true}
                          className="bg-black/20 border-cyan/30 text-white"
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {form.videoGenerationMode === "target" && (
                <div className="space-y-3">
                  <div className="space-y-2">
                    <Label className="text-cyan text-sm">Target Duration (s)</Label>
                    <NumberInput
                      value={form.videoTargetDuration}
                      onChange={(value) => updateForm({ videoTargetDuration: value })}
                      min={1}
                      variant="buttons"
                      hideLabel={true}
                      className="bg-black/20 border-cyan/30 text-white"
                    />
                  </div>
                  
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-2">
                      <Label className="text-cyan text-xs">Min FPS</Label>
                      <NumberInput
                        value={form.videoFpsMin}
                        onChange={(value) => updateForm({ videoFpsMin: value })}
                        min={1}
                        variant="buttons"
                        hideLabel={true}
                        className="bg-black/20 border-cyan/30 text-white"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-cyan text-xs">Max FPS</Label>
                      <NumberInput
                        value={form.videoFpsMax}
                        onChange={(value) => updateForm({ videoFpsMax: value })}
                        min={1}
                        variant="buttons"
                        hideLabel={true}
                        className="bg-black/20 border-cyan/30 text-white"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Video Quality */}
              <div className="space-y-2">
                <Label className="text-cyan text-sm">Quality</Label>
                <div className="grid grid-cols-1 gap-1">
                  {VIDEO_QUALITIES.map((quality) => (
                    <Button
                      key={quality.value}
                      type="button"
                      variant="outline"
                      onClick={() => updateForm({ videoQuality: quality.value as "low" | "medium" | "high" })}
                      className={cn(
                        "h-8 justify-start text-left text-xs transition-all duration-300",
                        form.videoQuality === quality.value
                          ? "bg-cyan/20 border-cyan text-cyan hover:bg-cyan/30"
                          : "bg-black/20 border-cyan/30 text-grey-light hover:bg-cyan/10 hover:border-cyan hover:text-white"
                      )}
                    >
                      <div>
                        <span className="font-medium">{quality.label}</span>
                        <span className="ml-2 opacity-70">({quality.desc})</span>
                      </div>
                    </Button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Video Automation */}
          <div className="space-y-3">
            <div className="flex items-center space-x-2">
              <Zap className="w-4 h-4 text-purple" />
              <Label className="text-white font-medium">Video Automation</Label>
            </div>
            
            <div className="p-4 bg-purple/5 border border-purple/20 rounded-lg space-y-4">
              <div className="space-y-3">
                <label className="flex items-center space-x-3 cursor-pointer">
                  <Checkbox
                    checked={form.videoManualOnly}
                    onCheckedChange={(checked) => {
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
                    }}
                  />
                  <span className="text-white text-sm">Manual Only</span>
                </label>

                <label className="flex items-center space-x-3 cursor-pointer">
                  <Checkbox
                    checked={form.videoPerCapture}
                    onCheckedChange={(checked) => {
                      if (checked) {
                        updateForm({ videoManualOnly: false, videoPerCapture: true })
                      } else {
                        updateForm({ videoPerCapture: false })
                      }
                    }}
                  />
                  <span className="text-white text-sm">Per-Capture Generation</span>
                </label>

                <label className="flex items-center space-x-3 cursor-pointer">
                  <Checkbox
                    checked={form.videoScheduled}
                    onCheckedChange={(checked) => {
                      if (checked) {
                        updateForm({ videoManualOnly: false, videoScheduled: true })
                      } else {
                        updateForm({ videoScheduled: false })
                      }
                    }}
                  />
                  <span className="text-white text-sm">Scheduled Generation</span>
                </label>

                <label className="flex items-center space-x-3 cursor-pointer">
                  <Checkbox
                    checked={form.videoMilestone}
                    onCheckedChange={(checked) => {
                      if (checked) {
                        updateForm({ videoManualOnly: false, videoMilestone: true })
                      } else {
                        updateForm({ videoMilestone: false })
                      }
                    }}
                  />
                  <span className="text-white text-sm">Milestone Generation</span>
                </label>
              </div>

              <div ref={automationConfigRef}>
                {form.videoMilestone && !form.videoManualOnly && (
                  <div className="p-3 bg-green-500/5 border border-green-500/20 rounded-lg space-y-3">
                    <Label className="text-green-400 text-sm">Generate every X images</Label>
                    <NumberInput
                      value={form.videoMilestoneInterval}
                      onChange={(value) => updateForm({ videoMilestoneInterval: value })}
                      min={1}
                      variant="buttons"
                      hideLabel={true}
                      className="bg-black/20 border-green-500/30 text-white"
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Warning for Running Timelapse */}
      {timelapse.status === "running" && (
        <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
          <div className="flex items-center gap-2 text-yellow-400 text-sm">
            <Info className="w-4 h-4" />
            <span className="font-medium">Note:</span>
            <span>Some settings changes may require stopping and restarting the timelapse to take effect.</span>
          </div>
        </div>
      )}
    </div>
  )
}