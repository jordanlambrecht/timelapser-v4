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
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { NumberInput } from "@/components/ui/number-input"
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"
import {
  Settings,
  Zap,
  Clock,
  Users,
  RefreshCw,
  HardDrive,
  AlertTriangle,
} from "lucide-react"
import { useSettings } from "@/contexts/settings-context"
import { toast } from "@/lib/toast"

export function ThumbnailJobSettingsCard() {
  const {
    thumbnailJobBatchSize = 10,
    thumbnailWorkerInterval = 3,
    thumbnailMaxRetries = 3,
    thumbnailHighLoadMode = false,
    thumbnailConcurrentJobs = 3,
    thumbnailMemoryLimit = 512,
    saving,
    updateSetting,
  } = useSettings()

  const [localSettings, setLocalSettings] = useState({
    thumbnailJobBatchSize,
    thumbnailWorkerInterval,
    thumbnailMaxRetries,
    thumbnailHighLoadMode,
    thumbnailConcurrentJobs,
    thumbnailMemoryLimit,
  })

  const [hasChanges, setHasChanges] = useState(false)

  const updateLocalSetting = (key: string, value: any) => {
    setLocalSettings((prev) => ({
      ...prev,
      [key]: value,
    }))
    setHasChanges(true)
  }

  const handleSave = async () => {
    try {
      // Save all thumbnail job settings
      await Promise.all([
        updateSetting(
          "thumbnail_job_batch_size",
          localSettings.thumbnailJobBatchSize.toString()
        ),
        updateSetting(
          "thumbnail_worker_interval",
          localSettings.thumbnailWorkerInterval.toString()
        ),
        updateSetting(
          "thumbnail_max_retries",
          localSettings.thumbnailMaxRetries.toString()
        ),
        updateSetting(
          "thumbnail_high_load_mode",
          localSettings.thumbnailHighLoadMode.toString()
        ),
        updateSetting(
          "thumbnail_concurrent_jobs",
          localSettings.thumbnailConcurrentJobs.toString()
        ),
        updateSetting(
          "thumbnail_memory_limit_mb",
          localSettings.thumbnailMemoryLimit.toString()
        ),
      ])

      setHasChanges(false)
      toast.success("Thumbnail job settings saved successfully")
    } catch (error) {
      console.error("Failed to save thumbnail job settings:", error)
      toast.error("Failed to save thumbnail job settings")
    }
  }

  const handleReset = () => {
    setLocalSettings({
      thumbnailJobBatchSize,
      thumbnailWorkerInterval,
      thumbnailMaxRetries,
      thumbnailHighLoadMode,
      thumbnailConcurrentJobs,
      thumbnailMemoryLimit,
    })
    setHasChanges(false)
  }

  const getPerformanceImpact = () => {
    const {
      thumbnailJobBatchSize: batch,
      thumbnailWorkerInterval: interval,
      thumbnailConcurrentJobs: concurrent,
    } = localSettings
    const throughputScore = (batch * concurrent) / Math.max(interval, 1)

    if (throughputScore >= 15)
      return { level: "high", color: "red", text: "High Performance" }
    if (throughputScore >= 8)
      return { level: "medium", color: "yellow", text: "Medium Performance" }
    return { level: "low", color: "green", text: "Low Performance" }
  }

  const performance = getPerformanceImpact()

  return (
    <Card className='glass border-purple-muted/30'>
      <CardHeader>
        <div className='flex items-center justify-between'>
          <div className='flex items-center space-x-3'>
            <div className='p-2 bg-gradient-to-br from-purple/20 to-pink/20 rounded-lg'>
              <Settings className='w-5 h-5 text-purple-light' />
            </div>
            <div>
              <CardTitle className='text-white'>
                Thumbnail Job Configuration
              </CardTitle>
              <CardDescription>
                Configure worker performance and resource usage for thumbnail
                generation
              </CardDescription>
            </div>
          </div>
          <Badge
            variant='outline'
            className={`border-${performance.color}-500/50 text-${performance.color}-400`}
          >
            {performance.text}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className='space-y-6'>
        {/* Performance Settings */}
        <div className='space-y-4'>
          <div className='flex items-center space-x-2'>
            <Zap className='w-4 h-4 text-yellow' />
            <h4 className='text-sm font-medium text-white'>
              Performance Settings
            </h4>
          </div>

          {/* Batch Size */}
          <div className='space-y-2'>
            <div className='flex items-center justify-between'>
              <Label htmlFor='batch-size' className='text-sm text-grey-light'>
                Batch Size (images per batch)
              </Label>
              <span className='text-sm text-white font-medium'>
                {localSettings.thumbnailJobBatchSize}
              </span>
            </div>
            <NumberInput
              id='batch-size'
              min={5}
              max={50}
              value={localSettings.thumbnailJobBatchSize}
              onChange={(value) =>
                updateLocalSetting("thumbnailJobBatchSize", value)
              }
              className='w-full'
            />
            <p className='text-xs text-grey-light/70'>
              Higher values process more images at once but use more memory
            </p>
          </div>

          {/* Worker Interval */}
          <div className='space-y-2'>
            <div className='flex items-center justify-between'>
              <Label
                htmlFor='worker-interval'
                className='text-sm text-grey-light'
              >
                Worker Interval (seconds)
              </Label>
              <span className='text-sm text-white font-medium'>
                {localSettings.thumbnailWorkerInterval}s
              </span>
            </div>
            <NumberInput
              id='worker-interval'
              min={1}
              max={60}
              value={localSettings.thumbnailWorkerInterval}
              onChange={(value) =>
                updateLocalSetting("thumbnailWorkerInterval", value)
              }
              className='w-full'
            />
            <p className='text-xs text-grey-light/70'>
              How often the worker checks for new jobs (lower = more responsive)
            </p>
          </div>

          {/* Concurrent Jobs */}
          <div className='space-y-2'>
            <div className='flex items-center justify-between'>
              <Label
                htmlFor='concurrent-jobs'
                className='text-sm text-grey-light'
              >
                Concurrent Jobs
              </Label>
              <span className='text-sm text-white font-medium'>
                {localSettings.thumbnailConcurrentJobs}
              </span>
            </div>
            <NumberInput
              id='concurrent-jobs'
              min={1}
              max={10}
              value={localSettings.thumbnailConcurrentJobs}
              onChange={(value) =>
                updateLocalSetting("thumbnailConcurrentJobs", value)
              }
              className='w-full'
            />
            <p className='text-xs text-grey-light/70'>
              Number of thumbnails processed simultaneously
            </p>
          </div>
        </div>

        <Separator className='bg-purple-muted/20' />

        {/* Reliability Settings */}
        <div className='space-y-4'>
          <div className='flex items-center space-x-2'>
            <RefreshCw className='w-4 h-4 text-cyan' />
            <h4 className='text-sm font-medium text-white'>
              Reliability Settings
            </h4>
          </div>

          {/* Max Retries */}
          <div className='space-y-2'>
            <Label htmlFor='max-retries' className='text-sm text-grey-light'>
              Maximum Retry Attempts
            </Label>
            <Input
              id='max-retries'
              type='number'
              min={1}
              max={10}
              value={localSettings.thumbnailMaxRetries}
              onChange={(e) =>
                updateLocalSetting(
                  "thumbnailMaxRetries",
                  parseInt(e.target.value) || 3
                )
              }
              className='bg-black/30 border-purple-muted/30 text-white'
            />
            <p className='text-xs text-grey-light/70'>
              How many times to retry failed thumbnail generation jobs
            </p>
          </div>

          {/* High Load Mode */}
          <div className='flex items-center justify-between space-x-3'>
            <div className='space-y-1'>
              <Label
                htmlFor='high-load-mode'
                className='text-sm text-grey-light'
              >
                Enable High Load Mode
              </Label>
              <p className='text-xs text-grey-light/70'>
                Automatically switch to aggressive processing when queue is busy
              </p>
            </div>
            <Switch
              id='high-load-mode'
              checked={localSettings.thumbnailHighLoadMode}
              onCheckedChange={(checked) =>
                updateLocalSetting("thumbnailHighLoadMode", checked)
              }
            />
          </div>
        </div>

        <Separator className='bg-purple-muted/20' />

        {/* Resource Settings */}
        <div className='space-y-4'>
          <div className='flex items-center space-x-2'>
            <HardDrive className='w-4 h-4 text-pink' />
            <h4 className='text-sm font-medium text-white'>Resource Limits</h4>
          </div>

          {/* Memory Limit */}
          <div className='space-y-2'>
            <div className='flex items-center justify-between'>
              <Label htmlFor='memory-limit' className='text-sm text-grey-light'>
                Memory Limit (MB)
              </Label>
              <span className='text-sm text-white font-medium'>
                {localSettings.thumbnailMemoryLimit} MB
              </span>
            </div>
            <NumberInput
              id='memory-limit'
              min={256}
              max={2048}
              value={localSettings.thumbnailMemoryLimit}
              onChange={(value) =>
                updateLocalSetting("thumbnailMemoryLimit", value)
              }
              className='w-full'
            />
            <p className='text-xs text-grey-light/70'>
              Maximum memory usage per thumbnail worker process
            </p>
          </div>
        </div>

        {/* Performance Warning */}
        {performance.level === "high" && (
          <div className='flex items-start space-x-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg'>
            <AlertTriangle className='w-4 h-4 text-red-400 mt-0.5 flex-shrink-0' />
            <div className='text-xs text-red-300'>
              <p className='font-medium'>High Performance Mode</p>
              <p>
                These settings may impact system performance. Monitor CPU and
                memory usage.
              </p>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className='flex items-center justify-between pt-4'>
          <div className='text-xs text-grey-light/70'>
            {hasChanges
              ? "You have unsaved changes"
              : "Settings are up to date"}
          </div>
          <div className='flex space-x-3'>
            <Button
              onClick={handleReset}
              variant='outline'
              size='sm'
              disabled={!hasChanges || saving}
              className='border-purple-muted/40 hover:bg-purple/20 text-white'
            >
              Reset
            </Button>
            <Button
              onClick={handleSave}
              disabled={!hasChanges || saving}
              className='bg-gradient-to-r from-purple to-pink hover:from-purple-dark hover:to-pink-dark text-white font-medium'
            >
              {saving ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
