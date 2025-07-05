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
import SwitchLabeled from "@/components/ui/switch-labeled"
import { Input } from "@/components/ui/input"
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
          <SwitchLabeled
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
                <SwitchLabeled
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
                <div className='flex items-center justify-between'>
                  <Label>Corruption Score Threshold</Label>
                  <span className='text-sm text-muted-foreground'>
                    {corruptionScoreThreshold}
                  </span>
                </div>
                <Input
                  type='number'
                  value={corruptionScoreThreshold}
                  onChange={(e) =>
                    setCorruptionScoreThreshold(parseInt(e.target.value) || 0)
                  }
                  min='0'
                  max='100'
                  step='5'
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
                  <SwitchLabeled
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
                  <SwitchLabeled
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
                  <Label className='text-sm'>Consecutive Failures</Label>
                  <Input
                    type='number'
                    value={corruptionDegradedConsecutiveThreshold}
                    onChange={(e) =>
                      setCorruptionDegradedConsecutiveThreshold(
                        parseInt(e.target.value) || 0
                      )
                    }
                    min='1'
                    max='50'
                  />
                  <div className='text-[0.8rem] text-muted-foreground'>
                    Failures in a row
                  </div>
                </div>

                <div className='space-y-2'>
                  <Label className='text-sm'>Time Window (minutes)</Label>
                  <Input
                    type='number'
                    value={corruptionDegradedTimeWindowMinutes}
                    onChange={(e) =>
                      setCorruptionDegradedTimeWindowMinutes(
                        parseInt(e.target.value) || 0
                      )
                    }
                    min='5'
                    max='1440'
                  />
                  <div className='text-[0.8rem] text-muted-foreground'>
                    Monitor period
                  </div>
                </div>

                <div className='space-y-2'>
                  <Label className='text-sm'>Failure Percentage</Label>
                  <Input
                    type='number'
                    value={corruptionDegradedFailurePercentage}
                    onChange={(e) =>
                      setCorruptionDegradedFailurePercentage(
                        parseInt(e.target.value) || 0
                      )
                    }
                    min='1'
                    max='100'
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
