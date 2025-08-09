// src/components/video-automation-badge.tsx
"use client"

import { VideoAutomationMode } from "@/types/video-automation"
import { Badge } from "@/components/ui/badge"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { Play, Clock, Target, Zap, Settings, Calendar } from "lucide-react"

interface VideoAutomationBadgeProps {
  mode: VideoAutomationMode
  schedule?: {
    type: "daily" | "weekly"
    time: string
    day?: string
  }
  milestoneConfig?: {
    enabled: boolean
    thresholds: number[]
  }
  className?: string
  showTooltip?: boolean
}

export function VideoAutomationBadge({
  mode,
  schedule,
  milestoneConfig,
  className = "",
  showTooltip = true,
}: VideoAutomationBadgeProps) {
  const getModeConfig = (mode: VideoAutomationMode) => {
    switch (mode) {
      case VideoAutomationMode.MANUAL:
        return {
          icon: <Play className='h-3 w-3' />,
          label: "Manual",
          variant: "secondary" as const,
          description: "Videos generated manually only",
        }
      case VideoAutomationMode.CONTINUOUS:
        return {
          icon: <Zap className='h-3 w-3' />,
          label: "Continuous",
          variant: "default" as const,
          description: "Generate video continuously",
        }
      case VideoAutomationMode.SCHEDULED:
        return {
          icon: <Clock className='h-3 w-3' />,
          label: "Scheduled",
          variant: "default" as const,
          description: getScheduleDescription(),
        }
      case VideoAutomationMode.MILESTONE:
        return {
          icon: <Target className='h-3 w-3' />,
          label: "Milestone",
          variant: "default" as const,
          description: getMilestoneDescription(),
        }
      default:
        return {
          icon: <Settings className='h-3 w-3' />,
          label: "Unknown",
          variant: "outline" as const,
          description: "Unknown automation mode",
        }
    }
  }

  const getScheduleDescription = () => {
    if (!schedule) return "Time-based generation"

    const time = schedule.time
    if (schedule.type === "daily") {
      return `Daily at ${time}`
    } else if (schedule.type === "weekly") {
      const day = schedule.day
        ? schedule.day.charAt(0).toUpperCase() + schedule.day.slice(1)
        : "Sunday"
      return `${day}s at ${time}`
    }
    return "Time-based generation"
  }

  const getMilestoneDescription = () => {
    if (!milestoneConfig?.enabled)
      return "Milestone-based generation (disabled)"

    const thresholds = milestoneConfig.thresholds
    if (thresholds.length === 0)
      return "Milestone-based generation (no thresholds)"

    const sortedThresholds = [...thresholds].sort((a, b) => a - b)
    if (sortedThresholds.length <= 3) {
      return `Generate at ${sortedThresholds.join(", ")} images`
    } else {
      return `Generate at ${sortedThresholds.slice(0, 2).join(", ")} and ${
        sortedThresholds.length - 2
      } more milestones`
    }
  }

  const config = getModeConfig(mode)

  const badgeContent = (
    <Badge
      variant={config.variant}
      className={`inline-flex items-center space-x-1 ${className}`}
    >
      {config.icon}
      <span>{config.label}</span>
    </Badge>
  )

  if (!showTooltip) {
    return badgeContent
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>{badgeContent}</TooltipTrigger>
        <TooltipContent>
          <div className='max-w-xs'>
            <p className='font-medium'>{config.label} Mode</p>
            <p className='text-xs text-muted-foreground mt-1'>
              {config.description}
            </p>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

interface VideoAutomationStatusProps {
  mode: VideoAutomationMode
  isActive?: boolean
  lastGenerated?: string
  queuePosition?: number
  className?: string
}

export function VideoAutomationStatus({
  mode,
  isActive = false,
  lastGenerated,
  queuePosition,
  className = "",
}: VideoAutomationStatusProps) {
  const getStatusColor = () => {
    if (mode === VideoAutomationMode.MANUAL) {
      return "text-gray-600 dark:text-gray-400"
    }
    return isActive
      ? "text-green-600 dark:text-green-400"
      : "text-orange-600 dark:text-orange-400"
  }

  const getStatusText = () => {
    if (mode === VideoAutomationMode.MANUAL) {
      return "Manual only"
    }

    if (queuePosition && queuePosition > 0) {
      return `In queue (#${queuePosition})`
    }

    if (isActive) {
      return "Active"
    }

    return "Waiting"
  }

  return (
    <div className={`flex items-center space-x-2 text-xs ${className}`}>
      <div
        className={`w-2 h-2 rounded-full ${
          mode === VideoAutomationMode.MANUAL
            ? "bg-gray-400"
            : isActive
            ? "bg-green-500 animate-pulse"
            : "bg-orange-500"
        }`}
      />
      <span className={getStatusColor()}>{getStatusText()}</span>
      {lastGenerated && (
        <span className='text-muted-foreground'>
          • Last: {new Date(lastGenerated).toLocaleDateString()}
        </span>
      )}
    </div>
  )
}
