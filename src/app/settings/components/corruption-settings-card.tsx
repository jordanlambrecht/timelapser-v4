// src/app/settings/components/corruption-settings-card.tsx
"use client"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { SuperSwitch } from "@/components/ui/switch"
import { NumberInput } from "@/components/ui/number-input"
import { Shield, Zap, AlertTriangle, Settings2 } from "lucide-react"
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"
import { useSettings } from "@/contexts/settings-context"

export function CorruptionSettingsCard() {
  const {
    corruptionDetectionEnabled,
    setCorruptionDetectionEnabled,
    corruptionScoreThreshold,
    setCorruptionScoreThreshold,
    corruptionAutoDiscardEnabled,
    setCorruptionAutoDiscardEnabled,
    corruptionAutoDisableDegraded,
    setCorruptionAutoDisableDegraded,
    corruptionDegradedConsecutiveThreshold,
    setCorruptionDegradedConsecutiveThreshold,
    corruptionDegradedTimeWindowMinutes,
    setCorruptionDegradedTimeWindowMinutes,
    corruptionDegradedFailurePercentage,
    setCorruptionDegradedFailurePercentage,
    corruptionHeavyDetectionEnabled,
    setCorruptionHeavyDetectionEnabled,
  } = useSettings()
  return (
    <Card>
      <CardHeader>
        <div className='flex items-center gap-2'>
          <Shield className='w-5 h-5 text-blue-400' />
          <CardTitle>Corruption Detection</CardTitle>
          <Badge variant={corruptionDetectionEnabled ? "default" : "secondary"}>
            {corruptionDetectionEnabled ? "Enabled" : "Disabled"}
          </Badge>
        </div>
        <CardDescription>
          Configure image corruption detection and automated quality monitoring
        </CardDescription>
      </CardHeader>
      <CardContent className='space-y-6'>
        {/* Master Enable/Disable */}
        <div className='flex items-center justify-between'>
          <div className='space-y-0.5'>
            <Label className='text-base'>Enable Corruption Detection</Label>
            <div className='text-[0.8rem] text-muted-foreground'>
              Master switch for all corruption detection features
            </div>
          </div>
          <SuperSwitch
            variant='labeled'
            checked={corruptionDetectionEnabled}
            onCheckedChange={setCorruptionDetectionEnabled}
            trueLabel='ON'
            falseLabel='OFF'
          />
        </div>

        {corruptionDetectionEnabled && (
          <>
            <Separator />

            {/* Heavy Detection Toggle */}
            <div className='space-y-4'>
              <div className='flex items-center gap-2'>
                <Zap className='w-4 h-4 text-amber-400' />
                <Label className='text-base'>Detection Algorithms</Label>
              </div>

              <div className='flex items-center justify-between'>
                <div className='space-y-0.5'>
                  <Label>Heavy Detection (Advanced CV)</Label>
                  <div className='text-[0.8rem] text-muted-foreground'>
                    Enable advanced computer vision algorithms (20-100ms
                    processing)
                  </div>
                </div>
                <SuperSwitch
                  variant='labeled'
                  checked={corruptionHeavyDetectionEnabled}
                  onCheckedChange={setCorruptionHeavyDetectionEnabled}
                  trueLabel='ON'
                  falseLabel='OFF'
                />
              </div>
            </div>

            <Separator />

            {/* Scoring Settings */}
            <div className='space-y-4'>
              <div className='flex items-center gap-2'>
                <Settings2 className='w-4 h-4 text-green-400' />
                <Label className='text-base'>Quality Thresholds</Label>
              </div>

              <div className='space-y-2'>
                <Label
                  htmlFor='corruption-score-threshold'
                  className='text-sm font-medium'
                >
                  Corruption Score Threshold
                </Label>
                <NumberInput
                  id='corruption-score-threshold'
                  value={corruptionScoreThreshold}
                  onChange={setCorruptionScoreThreshold}
                  min={0}
                  max={100}
                  step={5}
                  hideLabel={true}
                />
                <div className='text-[0.8rem] text-muted-foreground'>
                  Images below this score are considered corrupted (0-100)
                </div>
              </div>
            </div>

            <Separator />

            {/* Automated Actions */}
            <div className='space-y-4'>
              <div className='flex items-center gap-2'>
                <AlertTriangle className='w-4 h-4 text-orange-400' />
                <Label className='text-base'>Automated Actions</Label>
              </div>

              <div className='space-y-4'>
                <div className='flex items-center justify-between'>
                  <div className='space-y-0.5'>
                    <Label>Auto-discard Corrupted Images</Label>
                    <div className='text-[0.8rem] text-muted-foreground'>
                      Automatically delete images that fail quality checks
                    </div>
                  </div>
                  <SuperSwitch
                    variant='labeled'
                    checked={corruptionAutoDiscardEnabled}
                    onCheckedChange={setCorruptionAutoDiscardEnabled}
                    trueLabel='ON'
                    falseLabel='OFF'
                  />
                </div>

                <div className='flex items-center justify-between'>
                  <div className='space-y-0.5'>
                    <Label>Auto-disable Degraded Cameras</Label>
                    <div className='text-[0.8rem] text-muted-foreground'>
                      Automatically disable cameras with persistent corruption
                    </div>
                  </div>
                  <SuperSwitch
                    variant='labeled'
                    checked={corruptionAutoDisableDegraded}
                    onCheckedChange={setCorruptionAutoDisableDegraded}
                    trueLabel='ON'
                    falseLabel='OFF'
                  />
                </div>
              </div>
            </div>

            <Separator />

            {/* Degraded Mode Triggers */}
            <div className='space-y-4'>
              <Label className='text-base'>Degraded Mode Triggers</Label>

              <div className='grid grid-cols-1 md:grid-cols-3 gap-4'>
                <div className='space-y-2'>
                  <Label
                    htmlFor='consecutive-failures'
                    className='text-sm font-medium'
                  >
                    Consecutive Failures
                  </Label>
                  <NumberInput
                    id='consecutive-failures'
                    value={corruptionDegradedConsecutiveThreshold}
                    onChange={setCorruptionDegradedConsecutiveThreshold}
                    min={1}
                    max={50}
                    hideLabel={true}
                  />
                  <div className='text-[0.8rem] text-muted-foreground'>
                    Failures in a row
                  </div>
                </div>

                <div className='space-y-2'>
                  <Label htmlFor='time-window' className='text-sm font-medium'>
                    Time Window (minutes)
                  </Label>
                  <NumberInput
                    id='time-window'
                    value={corruptionDegradedTimeWindowMinutes}
                    onChange={setCorruptionDegradedTimeWindowMinutes}
                    min={5}
                    max={1440}
                    hideLabel={true}
                  />
                  <div className='text-[0.8rem] text-muted-foreground'>
                    Monitor period
                  </div>
                </div>

                <div className='space-y-2'>
                  <Label
                    htmlFor='failure-percentage'
                    className='text-sm font-medium'
                  >
                    Failure Percentage
                  </Label>
                  <NumberInput
                    id='failure-percentage'
                    value={corruptionDegradedFailurePercentage}
                    onChange={setCorruptionDegradedFailurePercentage}
                    min={1}
                    max={100}
                    hideLabel={true}
                  />
                  <div className='text-[0.8rem] text-muted-foreground'>
                    % of recent captures
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}
