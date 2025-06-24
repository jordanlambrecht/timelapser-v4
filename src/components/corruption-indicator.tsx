// src/components/corruption-indicator.tsx
"use client"

import { Badge } from "@/components/ui/badge"
import { AlertTriangle, Shield, CheckCircle, XCircle } from "lucide-react"
import { cn } from "@/lib/utils"
import type {
  CorruptionIndicatorProps,
  CorruptionAlertProps,
  CorruptionHealthSummaryProps,
} from "@/types"

export function CorruptionIndicator({
  score,
  degradedMode = false,
  size = "md",
  showLabel = false,
  className,
}: CorruptionIndicatorProps) {
  const getScoreColor = (score: number) => {
    if (score >= 90) return "text-green-500"
    if (score >= 70) return "text-blue-500"
    if (score >= 50) return "text-yellow-500"
    if (score >= 30) return "text-orange-500"
    return "text-red-500"
  }

  const getScoreLabel = (score: number) => {
    if (score >= 90) return "Excellent"
    if (score >= 70) return "Good"
    if (score >= 50) return "Fair"
    if (score >= 30) return "Poor"
    return "Critical"
  }

  const getIcon = () => {
    if (degradedMode) return <AlertTriangle className='h-4 w-4' />
    if (score >= 90) return <CheckCircle className='h-4 w-4' />
    if (score >= 70) return <Shield className='h-4 w-4' />
    return <XCircle className='h-4 w-4' />
  }

  const sizeClasses = {
    sm: "text-xs px-2 py-1",
    md: "text-sm px-3 py-1.5",
    lg: "text-base px-4 py-2",
  }

  if (degradedMode) {
    return (
      <Badge
        variant='destructive'
        className={cn("animate-pulse", sizeClasses[size], className)}
      >
        <AlertTriangle className='h-3 w-3 mr-1' />
        Degraded
      </Badge>
    )
  }

  return (
    <div className={cn("flex items-center space-x-2", className)}>
      <span
        className={cn("font-medium", getScoreColor(score), sizeClasses[size])}
      >
        Q: {score}/100
      </span>
      {showLabel && (
        <Badge
          variant='outline'
          className={cn("border-current", getScoreColor(score))}
        >
          {getIcon()}
          <span className='ml-1'>{getScoreLabel(score)}</span>
        </Badge>
      )}
    </div>
  )
}

export function CorruptionAlert({
  camera,
  onReset,
  className,
}: CorruptionAlertProps) {
  if (!camera.degraded_mode_active) return null

  return (
    <div
      className={cn(
        "bg-red-500/10 border border-red-500/20 rounded-lg p-3 space-y-2",
        className
      )}
    >
      <div className='flex items-center justify-between'>
        <div className='flex items-center space-x-2'>
          <AlertTriangle className='h-4 w-4 text-red-500' />
          <span className='font-medium text-red-500'>
            Quality Issues Detected
          </span>
        </div>
        {onReset && (
          <button
            onClick={() => onReset(camera.id)}
            className='text-xs px-2 py-1 bg-red-500/20 hover:bg-red-500/30 rounded'
          >
            Reset
          </button>
        )}
      </div>

      <div className='text-sm text-muted-foreground space-y-1'>
        <p>
          Camera "{camera.name}" has {camera.consecutive_corruption_failures}{" "}
          consecutive failures
        </p>
        <p>
          Lifetime issues: {camera.lifetime_glitch_count} | Recent quality:{" "}
          {camera.recent_avg_score}/100
        </p>
      </div>
    </div>
  )
}

export function CorruptionHealthSummary({
  stats,
  className,
}: CorruptionHealthSummaryProps) {
  const getHealthColor = (score: number) => {
    if (score >= 90) return "text-green-500"
    if (score >= 70) return "text-yellow-500"
    return "text-red-500"
  }

  const getHealthStatus = (score: number) => {
    if (score >= 90) return "Excellent"
    if (score >= 70) return "Good"
    if (score >= 50) return "Fair"
    return "Poor"
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* System Health Score */}
      <div className='text-center'>
        <div
          className={cn(
            "text-3xl font-bold",
            getHealthColor(stats.system_health_score)
          )}
        >
          {stats.system_health_score}/100
        </div>
        <p className='text-sm text-muted-foreground'>System Quality Health</p>
        <p
          className={cn(
            "text-sm font-medium",
            getHealthColor(stats.system_health_score)
          )}
        >
          {getHealthStatus(stats.system_health_score)}
        </p>
      </div>

      {/* Camera Status Breakdown */}
      <div className='grid grid-cols-3 gap-4 text-center'>
        <div>
          <div className='text-lg font-bold text-green-500'>
            {stats.cameras_healthy}
          </div>
          <p className='text-xs text-muted-foreground'>Healthy</p>
        </div>
        <div>
          <div className='text-lg font-bold text-red-500'>
            {stats.cameras_degraded}
          </div>
          <p className='text-xs text-muted-foreground'>Degraded</p>
        </div>
        <div>
          <div className='text-lg font-bold'>{stats.total_cameras}</div>
          <p className='text-xs text-muted-foreground'>Total</p>
        </div>
      </div>

      {/* Health Status Bar */}
      <div className='space-y-2'>
        <div className='flex justify-between text-xs text-muted-foreground'>
          <span>Camera Health Distribution</span>
          <span>
            {Math.round((stats.cameras_healthy / stats.total_cameras) * 100)}%
            Healthy
          </span>
        </div>
        <div className='flex h-2 rounded-full overflow-hidden bg-muted'>
          <div
            className='bg-green-500'
            style={{
              width: `${(stats.cameras_healthy / stats.total_cameras) * 100}%`,
            }}
          />
          <div
            className='bg-red-500'
            style={{
              width: `${(stats.cameras_degraded / stats.total_cameras) * 100}%`,
            }}
          />
        </div>
      </div>
    </div>
  )
}
