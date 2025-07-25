// src/components/timelapse-creation/slides/timelapse-configuration-slide.tsx
"use client"

import { useAutoAnimate } from "@formkit/auto-animate/react"
import { Input } from "@/components/ui/input"
import { NumberInput } from "@/components/ui/number-input"
import { Label } from "@/components/ui/label"
import { ToggleGroup } from "@/components/ui/toggle-group"
import { SuperSwitch } from "@/components/ui/switch"
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip"
import { Clock, Calendar, Sunrise, Sunset } from "lucide-react"
import { useSettings } from "@/contexts/settings-context"
import type { TimelapseForm } from "../timelapse-creation-modal"

interface TimelapseConfigurationSlideProps {
  form: TimelapseForm
  updateForm: (updates: Partial<TimelapseForm>) => void
  getMinDateTime: () => string
}

export function TimelapseConfigurationSlide({
  form,
  updateForm,
  getMinDateTime,
}: TimelapseConfigurationSlideProps) {
  const { sunriseSunsetEnabled } = useSettings()
  
  // AutoAnimate refs
  const [runWindowRef] = useAutoAnimate({ duration: 250 })
  const [stopTimeRef] = useAutoAnimate({ duration: 250 })

  return (
    <div className="px-1 space-y-8">
      <div className="text-center">
        <h3 className="text-xl font-semibold text-white mb-2">Timelapse Configuration</h3>
        <p className="text-grey-light/70">Configure your timelapse settings</p>
      </div>
      
      {/* Timelapse Name */}
      <div className="space-y-3">
        <Label htmlFor="timelapse-name" className="text-white font-medium">
          Timelapse Name
        </Label>
        <Input
          id="timelapse-name"
          value={form.name}
          onChange={(e) => updateForm({ name: e.target.value })}
          placeholder="Enter timelapse name..."
          className="bg-black/20 border-purple-muted/30 text-white placeholder:text-grey-light/50"
        />
      </div>

      {/* Run Window */}
      <div ref={runWindowRef} className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Clock className="w-4 h-4 text-cyan" />
            <Label className="text-white font-medium">Run Window</Label>
          </div>
          <SuperSwitch
            variant="labeled"
            checked={form.runWindowEnabled}
            onCheckedChange={(checked) => updateForm({ runWindowEnabled: checked })}
            trueLabel="Enabled"
            falseLabel="Disabled"
            colorTheme="pink"
          />
        </div>

        {form.runWindowEnabled && (
          <div className="space-y-4">
            {!sunriseSunsetEnabled ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <div>
                    <ToggleGroup
                      options={[
                        { label: "Between Times", value: "between" },
                        { 
                          label: "Sunrise/Sunset", 
                          value: "sunrise-sunset",
                          disabled: true
                        }
                      ]}
                      value={form.runWindowType}
                      onValueChange={(value) => updateForm({ runWindowType: value as "between" | "sunrise-sunset" })}
                      label="Window Type"
                      colorTheme="cyan"
                      borderFaded={true}
                    />
                  </div>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Enable sunrise/sunset in settings to use this option</p>
                </TooltipContent>
              </Tooltip>
            ) : (
              <ToggleGroup
                options={[
                  { label: "Between Times", value: "between" },
                  { label: "Sunrise/Sunset", value: "sunrise-sunset" }
                ]}
                value={form.runWindowType}
                onValueChange={(value) => updateForm({ runWindowType: value as "between" | "sunrise-sunset" })}
                label="Window Type"
                colorTheme="cyan"
                borderFaded={true}
              />
            )}

            {/* Time Window Controls */}
            {form.runWindowType === "between" && (
              <div className="p-4 bg-cyan/5 border border-cyan/20 rounded-lg">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-cyan text-sm">Start Time</Label>
                    <Input
                      type="time"
                      value={form.timeWindowStart}
                      onChange={(e) => updateForm({ timeWindowStart: e.target.value })}
                      className="bg-black/20 border-cyan/30 text-white"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-cyan text-sm">End Time</Label>
                    <Input
                      type="time"
                      value={form.timeWindowEnd}
                      onChange={(e) => updateForm({ timeWindowEnd: e.target.value })}
                      className="bg-black/20 border-cyan/30 text-white"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Sunrise/Sunset Controls */}
            {form.runWindowType === "sunrise-sunset" && (
              <div className="p-4 bg-yellow-500/5 border border-yellow-500/20 rounded-lg">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <div className="flex items-center space-x-2">
                      <Sunrise className="w-4 h-4 text-yellow-400" />
                      <Label className="text-yellow-400 text-sm">Sunrise Offset</Label>
                    </div>
                    <NumberInput
                      step={15}
                      value={form.sunriseOffsetMinutes}
                      onChange={(value) => updateForm({ sunriseOffsetMinutes: value })}
                      variant="buttons"
                      hideLabel={true}
                      className="bg-black/20 border-yellow-500/30 text-white"
                    />
                    <p className="text-xs text-yellow-400/70">
                      Minutes before (-) or after (+) sunrise
                    </p>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center space-x-2">
                      <Sunset className="w-4 h-4 text-orange-400" />
                      <Label className="text-orange-400 text-sm">Sunset Offset</Label>
                    </div>
                    <NumberInput
                      step={15}
                      value={form.sunsetOffsetMinutes}
                      onChange={(value) => updateForm({ sunsetOffsetMinutes: value })}
                      variant="buttons"
                      hideLabel={true}
                      className="bg-black/20 border-orange-500/30 text-white"
                    />
                    <p className="text-xs text-orange-400/70">
                      Minutes before (-) or after (+) sunset
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Stop Time */}
      <div ref={stopTimeRef} className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Calendar className="w-4 h-4 text-purple" />
            <Label className="text-white font-medium">Auto-Stop Recording</Label>
          </div>
          <SuperSwitch
            variant="labeled"
            checked={form.stopTimeEnabled}
            onCheckedChange={(checked) => updateForm({ stopTimeEnabled: checked })}
            trueLabel="Enabled"
            falseLabel="Disabled"
            colorTheme="pink"
          />
        </div>

        {form.stopTimeEnabled && (
          <div className="flex gap-6">
            <div className="flex-shrink-0 flex flex-col">
              <Label className="text-white font-medium mb-2">Stop Method</Label>
              <ToggleGroup
                options={[
                  { label: "Date & Time", value: "datetime" },
                  { label: "Day Count", value: "daycount" }
                ]}
                value={form.stopType}
                onValueChange={(value) => updateForm({ stopType: value as "datetime" | "daycount" })}
                label=""
                orientation="vertical"
                colorTheme="cyan"
                borderFaded={true}
              />
            </div>

            <div className="flex-1 flex flex-col">
              <Label className="text-white font-medium mb-2">Configuration</Label>
              {form.stopType === "datetime" && (
                <div className="p-4 bg-purple/5 border border-purple/20 rounded-lg space-y-2">
                  <Label className="text-purple text-sm">Stop Date & Time</Label>
                  <Input
                    type="datetime-local"
                    value={form.stopDateTime}
                    min={getMinDateTime()}
                    onChange={(e) => updateForm({ stopDateTime: e.target.value })}
                    className="bg-black/20 border-purple/30 text-white"
                  />
                </div>
              )}

              {form.stopType === "daycount" && (
                <div className="p-4 bg-purple/5 border border-purple/20 rounded-lg space-y-2">
                  <Label className="text-purple text-sm">Number of Days</Label>
                  <NumberInput
                    value={form.stopDayCount}
                    onChange={(value) => updateForm({ stopDayCount: value })}
                    min={1}
                    variant="buttons"
                    hideLabel={true}
                    className="bg-black/20 border-purple/30 text-white"
                  />
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}