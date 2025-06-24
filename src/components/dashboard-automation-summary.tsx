// src/components/dashboard-automation-summary.tsx
"use client"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import {
  Video,
  Clock,
  Target,
  Zap,
  Play,
  Activity,
  RefreshCw,
  ArrowRight,
} from "lucide-react"
import { useAutomationStats } from "@/hooks/use-video-automation"
import Link from "next/link"

interface DashboardAutomationSummaryProps {
  className?: string
}

export function DashboardAutomationSummary({
  className = "",
}: DashboardAutomationSummaryProps) {
  const { stats, isLoading, error, refresh } = useAutomationStats()

  if (error) {
    return (
      <Card className={className}>
        <CardContent className='flex items-center justify-center py-8'>
          <div className='text-center space-y-2'>
            <Video className='h-8 w-8 text-red-500 mx-auto' />
            <p className='text-sm text-muted-foreground'>
              Failed to load automation stats
            </p>
            <Button variant='outline' size='sm' onClick={refresh}>
              <RefreshCw className='h-3 w-3 mr-1' />
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (isLoading || !stats) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle className='flex items-center space-x-2'>
            <Video className='h-5 w-5' />
            <span>Video Automation</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className='flex items-center justify-center py-8'>
            <RefreshCw className='h-6 w-6 animate-spin' />
          </div>
        </CardContent>
      </Card>
    )
  }

  const getAutomationIcon = (mode: string) => {
    switch (mode) {
      case "manual":
        return <Play className='h-3 w-3' />
      case "per_capture":
        return <Zap className='h-3 w-3' />
      case "scheduled":
        return <Clock className='h-3 w-3' />
      case "milestone":
        return <Target className='h-3 w-3' />
      default:
        return <Video className='h-3 w-3' />
    }
  }

  const getModeLabel = (mode: string) => {
    switch (mode) {
      case "manual":
        return "Manual"
      case "per_capture":
        return "Per Capture"
      case "scheduled":
        return "Scheduled"
      case "milestone":
        return "Milestone"
      default:
        return mode
    }
  }

  const totalAutomatedCameras = Object.entries(stats.automation_modes)
    .filter(([mode]) => mode !== "manual")
    .reduce((sum, [, count]) => sum + count, 0)

  const totalTriggers = Object.values(stats.triggers_week).reduce(
    (sum, count) => sum + count,
    0
  )

  return (
    <Card className={className}>
      <CardHeader>
        <div className='flex items-center justify-between'>
          <div className='flex items-center space-x-2'>
            <Video className='h-5 w-5' />
            <div>
              <CardTitle>Video Automation</CardTitle>
              <CardDescription>
                Automated video generation overview
              </CardDescription>
            </div>
          </div>
          <Button variant='outline' size='sm' onClick={refresh}>
            <RefreshCw
              className={`h-3 w-3 mr-1 ${isLoading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </div>
      </CardHeader>

      <CardContent className='space-y-6'>
        {/* Queue Status */}
        <div className='grid grid-cols-2 md:grid-cols-4 gap-3'>
          <div className='text-center p-3 bg-blue-50 dark:bg-blue-950/20 rounded-lg'>
            <div className='text-lg font-bold text-blue-600 dark:text-blue-400'>
              {stats.queue.pending_jobs}
            </div>
            <p className='text-xs text-blue-700 dark:text-blue-300'>Pending</p>
          </div>

          <div className='text-center p-3 bg-orange-50 dark:bg-orange-950/20 rounded-lg'>
            <div className='text-lg font-bold text-orange-600 dark:text-orange-400'>
              {stats.queue.processing_jobs}
            </div>
            <p className='text-xs text-orange-700 dark:text-orange-300'>
              Processing
            </p>
          </div>

          <div className='text-center p-3 bg-green-50 dark:bg-green-950/20 rounded-lg'>
            <div className='text-lg font-bold text-green-600 dark:text-green-400'>
              {stats.queue.jobs_today}
            </div>
            <p className='text-xs text-green-700 dark:text-green-300'>Today</p>
          </div>

          <div className='text-center p-3 bg-purple-50 dark:bg-purple-950/20 rounded-lg'>
            <div className='text-lg font-bold text-purple-600 dark:text-purple-400'>
              {stats.queue.jobs_week}
            </div>
            <p className='text-xs text-purple-700 dark:text-purple-300'>
              This Week
            </p>
          </div>
        </div>

        <Separator />

        {/* Automation Modes Distribution */}
        <div className='space-y-3'>
          <div className='flex items-center space-x-2'>
            <Activity className='h-4 w-4' />
            <h4 className='font-medium'>Automation Modes</h4>
          </div>

          <div className='grid grid-cols-2 gap-2'>
            {Object.entries(stats.automation_modes).map(([mode, count]) => (
              <div
                key={mode}
                className='flex items-center justify-between p-2 border rounded'
              >
                <div className='flex items-center space-x-2'>
                  {getAutomationIcon(mode)}
                  <span className='text-sm'>{getModeLabel(mode)}</span>
                </div>
                <Badge variant={mode === "manual" ? "secondary" : "default"}>
                  {count}
                </Badge>
              </div>
            ))}
          </div>
        </div>

        {/* Summary Stats */}
        <div className='space-y-2'>
          <div className='flex items-center justify-between text-sm'>
            <span className='text-muted-foreground'>Automated Cameras:</span>
            <span className='font-medium'>{totalAutomatedCameras}</span>
          </div>
          <div className='flex items-center justify-between text-sm'>
            <span className='text-muted-foreground'>Triggers This Week:</span>
            <span className='font-medium'>{totalTriggers}</span>
          </div>
        </div>

        {/* Quick Actions */}
        <div className='flex gap-2'>
          <Button variant='outline' size='sm' className='flex-1' asChild>
            <Link href='/video-queue'>
              <Video className='h-3 w-3 mr-1' />
              View Queue
            </Link>
          </Button>
          <Button variant='outline' size='sm' className='flex-1' asChild>
            <Link href='/cameras'>
              <ArrowRight className='h-3 w-3 mr-1' />
              Configure
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
