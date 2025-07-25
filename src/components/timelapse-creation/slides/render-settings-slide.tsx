// src/components/timelapse-creation/slides/render-settings-slide.tsx
"use client"

import { Input } from "@/components/ui/input"
import { NumberInput } from "@/components/ui/number-input"
import { Label } from "@/components/ui/label"
import { ToggleGroup } from "@/components/ui/toggle-group"
import { Button } from "@/components/ui/button"
import { useAutoAnimate } from "@formkit/auto-animate/react"
import { Video, Settings, Play } from "lucide-react"
import { cn } from "@/lib/utils"
import { SuperSwitch } from "@/components/ui/switch"
import type { TimelapseForm } from "../timelapse-creation-modal"

interface RenderSettingsSlideProps {
  form: TimelapseForm
  updateForm: (updates: Partial<TimelapseForm>) => void
}

const VIDEO_QUALITIES = [
  { label: "Low", value: "low", desc: "720p, faster processing" },
  { label: "Medium", value: "medium", desc: "1080p, balanced quality" },
  { label: "High", value: "high", desc: "Original resolution, best quality" },
]


export function RenderSettingsSlide({
  form,
  updateForm,
}: RenderSettingsSlideProps) {
  const [modeConfigRef] = useAutoAnimate({ duration: 250 })

  // Calculate estimated video duration for standard mode
  const getEstimatedDuration = () => {
    if (!form.captureInterval) return "N/A"
    
    // Assume 1000 images as example (this would be dynamic in real implementation)
    const totalImages = 1000
    const duration = totalImages / form.videoStandardFps
    
    if (duration < 60) {
      return `~${Math.round(duration)}s`
    } else if (duration < 3600) {
      return `~${Math.round(duration / 60)}m ${Math.round(duration % 60)}s`
    } else {
      return `~${Math.round(duration / 3600)}h ${Math.round((duration % 3600) / 60)}m`
    }
  }

  // Calculate FPS for target mode
  const getCalculatedFPS = () => {
    if (!form.videoTargetDuration) return "N/A"
    
    const totalImages = 1000 // This would be dynamic
    const calculatedFPS = totalImages / form.videoTargetDuration
    
    const clampedFPS = Math.min(Math.max(calculatedFPS, form.videoFpsMin), form.videoFpsMax)
    return `${Math.round(clampedFPS)} FPS`
  }

  return (
    <div className="px-1 space-y-6">
      <div className="text-center">
        <h3 className="text-xl font-semibold text-white mb-2">Video Render Settings</h3>
        <p className="text-grey-light/70">Configure how your timelapse video will be generated</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column - Video Generation */}
        <div className="space-y-6">
          <div className="space-y-3">
            <div className="flex items-center space-x-2">
              <Video className="w-4 h-4 text-cyan" />
              <Label className="text-white font-medium">Video Generation</Label>
            </div>
            
            <div className="p-4 bg-cyan/5 border border-cyan/20 rounded-lg space-y-4">
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

              <div ref={modeConfigRef}>
                {form.videoGenerationMode === "standard" && (
                  <div className="space-y-4">
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
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div className="space-y-2">
                          <Label className="text-cyan text-xs">Min Duration (s)</Label>
                          <NumberInput
                            value={form.videoMinDuration}
                            onChange={(value) => updateForm({ videoMinDuration: value })}
                            min={1}
                            max={3600}
                            variant="buttons"
                            hideLabel={true}
                            className="bg-black/20 border-cyan/30 text-white"
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-cyan text-xs">Max Duration (s)</Label>
                          <NumberInput
                            value={form.videoMaxDuration}
                            onChange={(value) => updateForm({ videoMaxDuration: value })}
                            min={1}
                            max={3600}
                            variant="buttons"
                            hideLabel={true}
                            className="bg-black/20 border-cyan/30 text-white"
                          />
                        </div>
                      </div>
                    )}

                    <div className="p-3 bg-cyan/10 border border-cyan/30 rounded-lg">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-cyan">Estimated Duration:</span>
                        <span className="text-white font-medium">{getEstimatedDuration()}</span>
                      </div>
                    </div>
                  </div>
                )}

                {form.videoGenerationMode === "target" && (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label className="text-cyan text-sm">Target Duration (seconds)</Label>
                      <NumberInput
                        value={form.videoTargetDuration}
                        onChange={(value) => updateForm({ videoTargetDuration: value })}
                        min={1}
                        max={3600}
                        variant="buttons"
                        hideLabel={true}
                        className="bg-black/20 border-cyan/30 text-white"
                      />
                    </div>
                    
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div className="space-y-2">
                        <Label className="text-cyan text-xs">Min FPS</Label>
                        <NumberInput
                          value={form.videoFpsMin}
                          onChange={(value) => updateForm({ videoFpsMin: value })}
                          min={1}
                          max={60}
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
                          max={120}
                          variant="buttons"
                          hideLabel={true}
                          className="bg-black/20 border-cyan/30 text-white"
                        />
                      </div>
                    </div>

                    <div className="p-3 bg-cyan/10 border border-cyan/30 rounded-lg">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-cyan">Calculated FPS:</span>
                        <span className="text-white font-medium">{getCalculatedFPS()}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Video Quality */}
          <div className="space-y-3">
            <div className="flex items-center space-x-2">
              <Settings className="w-4 h-4 text-purple" />
              <Label className="text-white font-medium">Video Quality</Label>
            </div>
            
            <div className="p-4 bg-purple/5 border border-purple/20 rounded-lg">
              <div className="grid grid-cols-1 gap-2">
                {VIDEO_QUALITIES.map((quality) => (
                  <Button
                    key={quality.value}
                    type="button"
                    variant="outline"
                    onClick={() => updateForm({ videoQuality: quality.value as "low" | "medium" | "high" })}
                    className={cn(
                      "h-12 justify-start text-left transition-all duration-300",
                      form.videoQuality === quality.value
                        ? "bg-purple/20 border-purple text-purple hover:bg-purple/30"
                        : "bg-black/20 border-purple-muted/30 text-grey-light hover:bg-purple-dark/20 hover:border-purple-muted hover:text-white"
                    )}
                  >
                    <div>
                      <div className="font-medium">{quality.label}</div>
                      <div className="text-xs opacity-70">{quality.desc}</div>
                    </div>
                  </Button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column - Auto-Generated Naming Info */}
        <div className="space-y-6">
          <div className="space-y-3">
            <div className="flex items-center space-x-2">
              <Play className="w-4 h-4 text-green-400" />
              <Label className="text-white font-medium">Video Naming</Label>
            </div>
            
            <div className="p-4 bg-green-500/5 border border-green-500/20 rounded-lg">
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                  <span className="text-green-400 text-sm font-medium">Auto-Generated Names</span>
                </div>
                <p className="text-green-400/80 text-sm leading-relaxed">
                  Video names will be automatically generated based on your automation settings to prevent conflicts:
                </p>
                <div className="space-y-1 text-xs text-green-400/60">
                  <div>• Per-Capture: <span className="text-white">Timelapse_2024-01-15_PerCapture</span></div>
                  <div>• Scheduled: <span className="text-white">Timelapse_2024-01-15_Daily_18-00</span></div>
                  <div>• Milestone: <span className="text-white">Timelapse_2024-01-15_Milestone_500</span></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}