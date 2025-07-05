// src/app/settings/components/logging-settings-card.tsx
"use client"

import { useState } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { NumberInput } from "@/components/ui/number-input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { toast } from "@/lib/toast"
import SwitchLabeled from "@/components/ui/switch-labeled"
import { FileText } from "lucide-react"
import { useSettings } from "@/contexts/settings-context"

export function LoggingSettingsCard() {
  const {
    logRetentionDays,
    setLogRetentionDays,
    maxLogFileSize,
    setMaxLogFileSize,
    enableDebugLogging,
    setEnableDebugLogging,
    logLevel,
    setLogLevel,
    enableLogRotation,
    setEnableLogRotation,
    enableLogCompression,
    setEnableLogCompression,
    maxLogFiles,
    setMaxLogFiles,
  } = useSettings()
  // Local state for confirmation dialog
  const [cleanLogsConfirmOpen, setCleanLogsConfirmOpen] = useState(false)

  const handleCleanLogsNow = async () => {
    setCleanLogsConfirmOpen(false)
    toast.info("Cleaning logs...", {
      description: "System logs are being cleaned up",
      duration: 3000,
    })
    // TODO: Implement actual log cleanup functionality
  }

  return (
    <>
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
                    <SelectItem value='debug'>Debug (Most Verbose)</SelectItem>
                    <SelectItem value='info'>Info (Standard)</SelectItem>
                    <SelectItem value='warn'>
                      Warning (Important Only)
                    </SelectItem>
                    <SelectItem value='error'>Error (Critical Only)</SelectItem>
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
                  <Label htmlFor='log-rotation' className='text-sm font-medium'>
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
    </>
  )
}
