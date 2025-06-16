// src/components/ui/combined-status-badge.tsx
import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"
import { Pause, Square } from "lucide-react"
import { isWithinTimeWindow } from "@/lib/time-utils"

const statusBadgeVariants = cva(
  "inline-flex items-center space-x-2 text-xs font-medium px-3 py-1.5 rounded-full border transition-all duration-300 whitespace-nowrap",
  {
    variants: {
      status: {
        // Connection status variants
        online: "bg-success/20 text-success border-success/30",
        offline: "bg-failure/20 text-failure border-failure/30",
        unknown: "bg-warn/20 text-warn border-warn/30",

        // Action status variants
        recording: "bg-success/20 text-success border-success/30",
        snoozing: "bg-purple/20 text-purple-light border-purple/30",
        paused: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
        stopped: "bg-grey-light/10 text-grey-light border-grey-light/20",
      },
      size: {
        sm: "px-2 py-1 text-xs",
        md: "px-3 py-1.5 text-xs",
        lg: "px-4 py-2 text-sm",
      },
      animation: {
        none: "",
        pulse: "[&>*:first-child]:animate-pulse",
        glow: "[&>*:first-child]:animate-pulse [&>*:first-child]:shadow-lg",
      },
    },
    defaultVariants: {
      size: "md",
      animation: "none",
    },
  }
)

interface CombinedStatusBadgeProps
  extends VariantProps<typeof statusBadgeVariants> {
  healthStatus: "online" | "offline" | "unknown"
  timelapseStatus?: string
  isTimelapseRunning?: boolean
  timeWindowStart?: string
  timeWindowEnd?: string
  useTimeWindow?: boolean
  className?: string
}

export function CombinedStatusBadge({
  healthStatus,
  timelapseStatus,
  isTimelapseRunning,
  timeWindowStart = "06:00",
  timeWindowEnd = "18:00",
  useTimeWindow = false,
  size = "md",
  className,
}: CombinedStatusBadgeProps) {
  // For offline cameras, only show connection status
  if (healthStatus === "offline" || healthStatus === "unknown") {
    return (
      <div
        className={cn(
          statusBadgeVariants({
            status: healthStatus,
            size,
            animation: "pulse",
          }),
          className
        )}
      >
        <span>●</span>
        <span className='capitalize'>{healthStatus}</span>
      </div>
    )
  }

  // For online cameras, determine combined status
  const isTimelapsePaused = timelapseStatus === "paused"
  const isTimelapseStopped = !timelapseStatus || timelapseStatus === "stopped"

  // Determine status and content
  let statusVariant: "recording" | "snoozing" | "paused" | "stopped"
  let icon: React.ReactNode
  let label: string
  let shouldAnimate = false

  if (isTimelapseRunning) {
    const isWithinTime = isWithinTimeWindow({
      start: timeWindowStart,
      end: timeWindowEnd,
      enabled: useTimeWindow,
    })

    if (isWithinTime) {
      statusVariant = "recording"
      icon = <div className='w-2 h-2 rounded-full bg-success' />
      label = "Recording"
      shouldAnimate = true
    } else {
      statusVariant = "snoozing"
      icon = <div className='w-2 h-2 rounded-full bg-purple-light' />
      label = "Snoozing"
      shouldAnimate = true
    }
  } else if (isTimelapsePaused) {
    statusVariant = "paused"
    icon = <Pause className='w-3 h-3' />
    label = "Paused"
  } else {
    statusVariant = "stopped"
    icon = <Square className='w-3 h-3' />
    label = "Stopped"
  }

  return (
    <div
      className={cn(
        statusBadgeVariants({
          status: statusVariant,
          size,
          animation: shouldAnimate ? "glow" : "none",
        }),
        className
      )}
    >
      {icon}
      <span>{label}</span>
    </div>
  )
}

// Legacy compatibility - can be used for connection-only status
export function StatusBadge({
  status,
  size = "md",
  className,
}: {
  status: "online" | "offline" | "unknown"
  size?: "sm" | "md" | "lg"
  className?: string
}) {
  return (
    <div
      className={cn(
        statusBadgeVariants({
          status,
          size,
          animation: status !== "unknown" ? "pulse" : "none",
        }),
        className
      )}
    >
      <span>●</span>
      <span className='capitalize'>{status}</span>
    </div>
  )
}

// Alias for backward compatibility and clearer naming
export const ConnectionStatusBadge = StatusBadge

export { statusBadgeVariants }
export type { CombinedStatusBadgeProps }
