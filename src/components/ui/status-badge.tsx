// src/components/ui/status-badge.tsx
import { cn } from "@/lib/utils"
import { Pause, Square, Circle } from "lucide-react"
import { isWithinTimeWindow } from "@/lib/time-utils"

interface StatusBadgeProps {
  healthStatus: "online" | "offline" | "unknown"
  timelapseStatus?: string
  isTimelapseRunning?: boolean
  timeWindowStart?: string
  timeWindowEnd?: string
  useTimeWindow?: boolean
  className?: string
}

export function StatusBadge({
  healthStatus,
  timelapseStatus,
  isTimelapseRunning,
  timeWindowStart = "06:00",
  timeWindowEnd = "18:00",
  useTimeWindow = false,
  className,
}: StatusBadgeProps) {
  // For offline cameras, only show connection status
  if (healthStatus === "offline" || healthStatus === "unknown") {
    return (
      <div
        className={cn(
          "inline-flex items-center space-x-2 text-xs font-medium px-3 py-1.5 rounded-full border transition-all duration-300 whitespace-nowrap",
          healthStatus === "offline"
            ? "bg-failure/20 text-failure border-failure/30 animate-pulse"
            : "bg-warn/20 text-warn border-warn/30 animate-pulse",
          className
        )}
      >
        <Circle className='w-2 h-2 fill-current' />
        <span className='capitalize'>{healthStatus}</span>
      </div>
    )
  }

  // For online cameras, determine combined status
  const isTimelapsePaused = timelapseStatus === "paused"
  const isTimelapseCompleted = !timelapseStatus || timelapseStatus === "completed"

  if (isTimelapseRunning) {
    const isWithinTime = isWithinTimeWindow({
      start: timeWindowStart,
      end: timeWindowEnd,
      enabled: useTimeWindow,
    })

    if (isWithinTime) {
      return (
        <div
          className={cn(
            "inline-flex items-center space-x-2 text-xs font-medium px-3 py-1.5 rounded-full border transition-all duration-300 whitespace-nowrap",
            "bg-success/20 text-success border-success/30 animate-pulse shadow-sm shadow-success/20",
            className
          )}
        >
          <Circle className='w-2 h-2 fill-current animate-pulse' />
          <span>Recording</span>
        </div>
      )
    } else {
      return (
        <div
          className={cn(
            "inline-flex items-center space-x-2 text-xs font-medium px-3 py-1.5 rounded-full border transition-all duration-300 whitespace-nowrap",
            "bg-purple/20 text-purple-light border-purple/30 animate-pulse shadow-sm shadow-purple/20",
            className
          )}
        >
          <Circle className='w-2 h-2 fill-current animate-pulse' />
          <span>Snoozing</span>
        </div>
      )
    }
  }

  if (isTimelapsePaused) {
    return (
      <div
        className={cn(
          "inline-flex items-center space-x-2 text-xs font-medium px-3 py-1.5 rounded-full border transition-all duration-300 whitespace-nowrap",
          "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
          className
        )}
      >
        <Pause className='w-3 h-3' />
        <span>Paused</span>
      </div>
    )
  }

  return (
    <div
      className={cn(
        "inline-flex items-center space-x-2 text-xs font-medium px-3 py-1.5 rounded-full border transition-all duration-300 whitespace-nowrap",
        "bg-cyan/20 text-cyan border-cyan/30",
        className
      )}
    >
      <Circle className='w-3 h-3' />
      <span>Completed</span>
    </div>
  )
}

// Alias for backward compatibility
export const CombinedStatusBadge = StatusBadge
