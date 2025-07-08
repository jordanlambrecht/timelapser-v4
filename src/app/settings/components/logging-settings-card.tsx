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
import { Database, FileText, HardDrive, Server } from "lucide-react"
import { useSettings } from "@/contexts/settings-context"

export function LoggingSettingsCard() {
  const {
    dbLogRetentionDays,
    setDbLogRetentionDays,
    fileLogRetentionDays,
    setFileLogRetentionDays,
    maxLogFileSize,
    setMaxLogFileSize,
    dbLogLevel,
    setDbLogLevel,
    fileLogLevel,
    setFileLogLevel,
    enableLogRotation,
    setEnableLogRotation,
    enableLogCompression,
    setEnableLogCompression,
    maxLogFiles,
    setMaxLogFiles,
  } = useSettings()

  // Local state for confirmation dialog
  const [cleanDbLogsConfirmOpen, setCleanDbLogsConfirmOpen] = useState(false)

  const handleCleanDbLogsNow = async () => {
    setCleanDbLogsConfirmOpen(false)

    try {
      toast.info("Cleaning database logs...", {
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
        toast.success("Database logs cleaned successfully! 🧹", {
          description: `Removed ${deletedCount} log entries`,
          duration: 5000,
        })
      } else {
        throw new Error(result.message || "Failed to clean logs")
      }
    } catch (error) {
      console.error("Failed to clean database logs:", error)
      toast.error("Failed to clean database logs", {
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        duration: 5000,
      })
    }
  }

  return (
    <>
      <div className='space-y-6'>
        {/* Database Logs Section */}
        <Card className='transition-all duration-300 glass hover:glow border-blue-500/20'>
          <CardHeader>
            <CardTitle className='flex items-center space-x-2'>
              <Database className='w-5 h-5 text-blue-400' />
              <span>Database Logs</span>
              <Badge
                variant='outline'
                className='text-xs border-blue-400/50 text-blue-300'
              >
                Application Events
              </Badge>
            </CardTitle>
            <CardDescription>
              Application events stored in PostgreSQL - captures, errors,
              corruption detection, user actions
            </CardDescription>
          </CardHeader>
          <CardContent className='space-y-4'>
            <div className='space-y-3'>
              <div className='flex items-center justify-between'>
                <div className='space-y-1'>
                  <Label className='text-sm font-medium'>
                    Database Cleanup
                  </Label>
                  <p className='text-xs text-muted-foreground'>
                    Remove ALL application event logs from PostgreSQL
                  </p>
                </div>
                <Button
                  type='button'
                  variant='outline'
                  size='sm'
                  onClick={() => setCleanDbLogsConfirmOpen(true)}
                  className='border-blue-500/50 text-blue-300 hover:bg-blue-500/20 hover:text-white hover:border-blue-400'
                >
                  <Database className='w-4 h-4 mr-2' />
                  Clean DB Logs
                </Button>
              </div>
            </div>

            <div className='space-y-4 p-4 rounded-lg bg-background/30 border border-blue-500/20'>
              <Label className='text-sm font-medium'>
                Database Log Configuration
              </Label>

              <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
                <div className='flex flex-col justify-between gap-y-2'>
                  <NumberInput
                    id='db-log-retention'
                    label='Retention Period (days)'
                    value={dbLogRetentionDays}
                    onChange={setDbLogRetentionDays}
                    min={1}
                    max={365}
                    className='bg-background/50 border-blue-500/30 focus:border-blue-400/50'
                  />
                  <p className='text-xs text-muted-foreground'>
                    How long to keep application events in the database
                  </p>
                </div>

                <div className='space-y-2'>
                  <Label
                    htmlFor='db-log-level'
                    className='text-xs text-muted-foreground'
                  >
                    Database Log Level
                  </Label>
                  <Select value={dbLogLevel} onValueChange={setDbLogLevel}>
                    <SelectTrigger className='bg-background/50 border-blue-500/30 focus:border-blue-400/50'>
                      <SelectValue placeholder='Select log level' />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value='debug'>
                        Debug (Most Verbose)
                      </SelectItem>
                      <SelectItem value='info'>Info (Standard)</SelectItem>
                      <SelectItem value='warn'>
                        Warning (Important Only)
                      </SelectItem>
                      <SelectItem value='error'>
                        Error (Critical Only)
                      </SelectItem>
                    </SelectContent>
                  </Select>
                  <p className='text-xs text-muted-foreground'>
                    Minimum level for events saved to database
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* File Logs Section */}
        <Card className='transition-all duration-300 glass hover:glow border-green-500/20'>
          <CardHeader>
            <CardTitle className='flex items-center space-x-2'>
              <HardDrive className='w-5 h-5 text-green-400' />
              <span>File Logs</span>
              <Badge
                variant='outline'
                className='text-xs border-green-400/50 text-green-300'
              >
                System Debugging
              </Badge>
            </CardTitle>
            <CardDescription>
              System debugging logs managed by loguru - worker processes,
              detailed debugging, local file rotation
            </CardDescription>
          </CardHeader>
          <CardContent className='space-y-4'>
            <div className='space-y-4 p-4 rounded-lg bg-background/30 border border-green-500/20'>
              <Label className='text-sm font-medium'>
                File Log Configuration
              </Label>

              <div className='grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4'>
                <div className='flex flex-col justify-between gap-y-2'>
                  <NumberInput
                    id='file-log-retention'
                    label='Retention Period (days)'
                    value={fileLogRetentionDays}
                    onChange={setFileLogRetentionDays}
                    min={1}
                    max={30}
                    className='bg-background/50 border-green-500/30 focus:border-green-400/50'
                  />
                  <p className='text-xs text-muted-foreground'>
                    How long to keep system debug files
                  </p>
                </div>

                <div className='flex flex-col justify-between gap-y-2'>
                  <NumberInput
                    id='max-log-size'
                    label='Max File Size (MB)'
                    value={maxLogFileSize}
                    onChange={setMaxLogFileSize}
                    min={1}
                    max={1000}
                    className='bg-background/50 border-green-500/30 focus:border-green-400/50'
                  />
                  <p className='text-xs text-muted-foreground'>
                    When to rotate log files
                  </p>
                </div>

                <div className='flex flex-col justify-between gap-y-2'>
                  <NumberInput
                    id='max-log-files'
                    label='Max Rotated Files'
                    value={maxLogFiles}
                    onChange={setMaxLogFiles}
                    min={1}
                    max={50}
                    className='bg-background/50 border-green-500/30 focus:border-green-400/50'
                  />
                  <p className='text-xs text-muted-foreground'>
                    How many rotated files to keep
                  </p>
                </div>
              </div>

              <div className='grid grid-cols-1 md:grid-cols-2 gap-4'>
                <div className='space-y-2'>
                  <Label
                    htmlFor='file-log-level'
                    className='text-xs text-muted-foreground'
                  >
                    File Log Level
                  </Label>
                  <Select value={fileLogLevel} onValueChange={setFileLogLevel}>
                    <SelectTrigger className='bg-background/50 border-green-500/30 focus:border-green-400/50'>
                      <SelectValue placeholder='Select log level' />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value='debug'>
                        Debug (Most Verbose)
                      </SelectItem>
                      <SelectItem value='info'>Info (Standard)</SelectItem>
                      <SelectItem value='warn'>
                        Warning (Important Only)
                      </SelectItem>
                      <SelectItem value='error'>
                        Error (Critical Only)
                      </SelectItem>
                    </SelectContent>
                  </Select>
                  <p className='text-xs text-muted-foreground'>
                    Minimum level for file logging
                  </p>
                </div>
              </div>

              <div className='space-y-3'>
                <div className='flex items-center justify-between'>
                  <div className='space-y-1'>
                    <Label
                      htmlFor='log-rotation'
                      className='text-sm font-medium'
                    >
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
      </div>

      {/* Clean Database Logs Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={cleanDbLogsConfirmOpen}
        onClose={() => setCleanDbLogsConfirmOpen(false)}
        onConfirm={handleCleanDbLogsNow}
        title='Clean Database Logs'
        description='Are you sure you want to clean up ALL database logs? This will remove ALL application event logs from PostgreSQL and cannot be undone.'
        confirmLabel='Yes, Clean Database Logs'
        cancelLabel='Cancel'
        variant='warning'
        icon={<Database className='w-6 h-6' />}
      />
    </>
  )
}
