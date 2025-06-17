// src/components/ui/combined-status-badge.tsx
import { cn } from "@/lib/utils"
import { Pause, Square } from "lucide-react"
import { isWithinTimeWindow } from "@/lib/time-utils"

interface CombinedStatusBadgeProps {
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
  className,
}: CombinedStatusBadgeProps) {
  // Handle offline/unknown cameras
  if (healthStatus === "offline" || healthStatus === "unknown") {
    const badgeClass = healthStatus === "offline" 
      ? "bg-failure/20 text-failure border-failure/30" 
      : "bg-warn/20 text-warn border-warn/30"
    
    return (
      <div
        className={cn(
          "inline-flex items-center space-x-2 text-xs font-medium px-3 py-1.5 rounded-full border transition-all duration-300",
          badgeClass,
          "[&>*:first-child]:animate-pulse",
          className
        )}
      >
        <span>●</span>
        <span className="capitalize">{healthStatus}</span>
      </div>
    )
  }

  // For online cameras, determine combined status
  let statusClass: string
  let icon: React.ReactNode
  let label: string
  let shouldAnimate = false

  switch (timelapseStatus) {
    case "running":
      const isWithinTime = isWithinTimeWindow({
        start: timeWindowStart,
        end: timeWindowEnd,
        enabled: useTimeWindow,
      })

      if (isWithinTime) {
        statusClass = "bg-success/20 text-success border-success/30"
        icon = <div className="w-2 h-2 rounded-full bg-success" />
        label = "Recording"
        shouldAnimate = true
      } else {
        statusClass = "bg-purple/20 text-purple-light border-purple/30"
        icon = <div className="w-2 h-2 rounded-full bg-purple-light" />
        label = "Snoozing"
        shouldAnimate = true
      }
      break

    case "paused":
      statusClass = "bg-yellow-500/20 text-yellow-400 border-yellow-500/30"
      icon = <Pause className="w-3 h-3" />
      label = "Paused"
      break

    default:
      statusClass = "bg-grey-light/10 text-grey-light border-grey-light/20"
      icon = <Square className="w-3 h-3" />
      label = "Stopped"
      break
  }

  return (
    <div
      className={cn(
        "inline-flex items-center space-x-2 text-xs font-medium px-3 py-1.5 rounded-full border transition-all duration-300",
        statusClass,
        shouldAnimate && "[&>*:first-child]:animate-pulse [&>*:first-child]:shadow-lg",
        className
      )}
    >
      {icon}
      <span>{label}</span>
    </div>
  )
}

// Simple status badge for connection status only
export function StatusBadge({
  status,
  className,
}: {
  status: "online" | "offline" | "unknown"
  className?: string
}) {
  const statusClass = 
    status === "online" ? "bg-success/20 text-success border-success/30" :
    status === "offline" ? "bg-failure/20 text-failure border-failure/30" :
    "bg-warn/20 text-warn border-warn/30"

  return (
    <div
      className={cn(
        "inline-flex items-center space-x-2 text-xs font-medium px-3 py-1.5 rounded-full border transition-all duration-300",
        statusClass,
        status !== "unknown" && "[&>*:first-child]:animate-pulse",
        className
      )}
    >
      <span>●</span>
      <span className="capitalize">{status}</span>
    </div>
  )
}

export const ConnectionStatusBadge = StatusBadge
