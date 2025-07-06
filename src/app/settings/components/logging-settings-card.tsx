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
import { SuperSwitch } from "@/components/ui/switch"
import { FileText } from "lucide-react"
import { useSettings } from "@/contexts/settings-context"

export function LoggingSettingsCard() {
  const {
    logRetentionDays,
    setLogRetentionDays,
    maxLogFileSize,
    setMaxLogFileSize,
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

    try {
      toast.info("Cleaning all logs...", {
        description: "Removing ALL log entries from the database",
        duration: 3000,
      })

      const response = await fetch(`/api/logs/cleanup?days_to_keep=0`, {
        method: "DELETE",
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const result = await response.json()

      if (result.success) {
        const deletedCount = result.data?.deleted_count || 0
        toast.success("All logs cleaned successfully! 🧹", {
          description: `Removed ${deletedCount} log entries`,
          duration: 5000,
        })
      } else {
        throw new Error(result.message || "Failed to clean logs")
      }
    } catch (error) {
      console.error("Failed to clean logs:", error)
      toast.error("Failed to clean logs", {
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        duration: 5000,
      })
    }
  }

  return (
    <>
      <Card className='transition-all duration-300 glass hover:glow'>
        <CardHeader>
          <CardTitle className='flex items-center space-x-2'>
            <FileText className='w-5 h-5 text-green-400' />
            <span>System Maintenance</span>
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
                  Remove ALL log entries from the database
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
                  <Label htmlFor='log-rotation' className='text-sm font-medium'>
                    Log Rotation
                  </Label>
                  <p className='text-xs text-muted-foreground'>
                    Automatically rotate logs when they reach max size
                  </p>
                </div>
                <SuperSwitch
                  variant='labeled'
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
                <SuperSwitch
                  variant='labeled'
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
        description='Are you sure you want to clean up ALL system logs? This will remove ALL log entries from the database and cannot be undone.'
        confirmLabel='Yes, Clean Logs'
        cancelLabel='Cancel'
        variant='warning'
        icon={<FileText className='w-6 h-6' />}
      />
    </>
  )
}
