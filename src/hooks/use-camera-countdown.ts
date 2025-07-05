// src/hooks/use-camera-countdown.ts
/**
 * Simplified camera countdown hook - focuses only on countdown logic
 * Uses centralized settings context for configuration
 */

import { useState, useEffect, useCallback, useMemo } from "react"
import {
  formatCountdown,
  formatRelativeTime,
  formatAbsoluteTimeForCounter,
  getSmartRefreshInterval,
  parseCaptureInterval,
  isNowState,
  type CaptureTimestamp,
  type TimeWindow,
} from "@/lib/time-utils"
import { useTimezoneSettings } from "@/contexts/settings-context"

interface CameraCountdownProps {
  camera: {
    id: number
    last_capture_at?: string | null
    next_capture_at?: string | null
    time_window_start?: string | null
    time_window_end?: string | null
    use_time_window?: boolean
  }
  timelapse?: {
    status: string
    last_capture_at?: string | null
  }
  captureInterval?: number | string
  enabled?: boolean
}

interface CountdownState {
  countdown: string
  lastCaptureText: string
  lastCaptureAbsolute: string
  nextCaptureAbsolute: string
  isOverdue: boolean
  isWithinWindow: boolean
  isNow: boolean
  refreshInterval: number
  captureProgress: number // 0-100 percentage of capture interval completed
}

export function useCameraCountdown({
  camera,
  timelapse,
  captureInterval = 300,
  enabled = true,
}: CameraCountdownProps): CountdownState {
  const [countdown, setCountdown] = useState<string>("")
  const [lastCaptureText, setLastCaptureText] = useState<string>("Never")
  const [lastCaptureAbsolute, setLastCaptureAbsolute] = useState<string>("")
  const [nextCaptureAbsolute, setNextCaptureAbsolute] = useState<string>("")

  // Get timezone from centralized settings
  const { timezone } = useTimezoneSettings()

  // Parse capture interval and create timestamp data
  const timestampData = useMemo((): CaptureTimestamp => {
    const interval = parseCaptureInterval(captureInterval)

    const timeWindow: TimeWindow | undefined =
      camera.use_time_window && camera.time_window_start
        ? {
            start: camera.time_window_start,
            end: camera.time_window_end || "18:00:00",
            enabled: camera.use_time_window,
          }
        : undefined

    return {
      lastCapture: camera.last_capture_at || timelapse?.last_capture_at,
      nextCapture: camera.next_capture_at,
      captureInterval: interval,
      timeWindow,
      timezone,
    }
  }, [
    camera.last_capture_at,
    camera.next_capture_at,
    camera.time_window_start,
    camera.time_window_end,
    camera.use_time_window,
    timelapse?.last_capture_at,
    captureInterval,
    timezone,
  ])

  // Determine timelapse status
  const status = useMemo(() => {
    if (!timelapse) return "stopped"
    switch (timelapse.status) {
      case "running":
        return "running"
      case "paused":
        return "paused"
      default:
        return "stopped"
    }
  }, [timelapse?.status])

  // Calculate refresh interval
  const refreshInterval = useMemo(() => {
    if (!enabled) return 60000 // 1 minute when disabled
    return getSmartRefreshInterval(timestampData, status)
  }, [timestampData, status, enabled])

  // Update countdown and last capture text
  const updateDisplay = useCallback(() => {
    if (!enabled) {
      setCountdown("Disabled")
      setLastCaptureText("Never")
      setLastCaptureAbsolute("")
      setNextCaptureAbsolute("")
      return
    }

    // Check if we're in "Now" state
    const inNowState = isNowState(timestampData, status)

    if (inNowState) {
      // Both should show "Now" when capture is happening
      setCountdown("Now")
      setLastCaptureText("Now")
      setLastCaptureAbsolute("")
      setNextCaptureAbsolute("")
      return
    }

    // Update countdown - pass timezone in options
    const countdownText = formatCountdown(timestampData, status, {
      timezone: timestampData.timezone,
    })
    setCountdown(countdownText)

    // Update last capture text - pass timezone in options
    const lastCaptureTimestamp = timestampData.lastCapture
    const relativeTime = formatRelativeTime(lastCaptureTimestamp, {
      includeAbsolute: false,
      includeSeconds: true,
      timezone: timestampData.timezone,
    })
    setLastCaptureText(relativeTime)

    // Update absolute time displays
    const lastAbsolute = formatAbsoluteTimeForCounter(
      lastCaptureTimestamp,
      timestampData.timezone
    )
    setLastCaptureAbsolute(lastAbsolute)

    const nextAbsolute = formatAbsoluteTimeForCounter(
      timestampData.nextCapture,
      timestampData.timezone
    )
    setNextCaptureAbsolute(nextAbsolute)
  }, [timestampData, status, enabled])

  // Set up timer with smart refresh interval
  useEffect(() => {
    if (!enabled) {
      updateDisplay()
      return
    }

    // Update immediately
    updateDisplay()

    // Set up timer
    const timer = setInterval(updateDisplay, refreshInterval)

    return () => clearInterval(timer)
  }, [updateDisplay, refreshInterval, enabled])

  // Determine additional state
  const isOverdue = useMemo(() => {
    if (status !== "running" || !timestampData.nextCapture) return false

    try {
      const nextTime = new Date(timestampData.nextCapture)
      const now = new Date()
      return now.getTime() > nextTime.getTime() + 60000 // 1 minute grace period
    } catch {
      return false
    }
  }, [timestampData.nextCapture, status])

  const isWithinWindow = useMemo(() => {
    if (!timestampData.timeWindow?.enabled) return true

    try {
      const now = new Date()
      const currentMinutes = now.getHours() * 60 + now.getMinutes()

      const [startHour, startMin] = timestampData.timeWindow.start
        .split(":")
        .map(Number)
      const [endHour, endMin] = (timestampData.timeWindow.end || "18:00:00")
        .split(":")
        .map(Number)

      const startMinutes = startHour * 60 + startMin
      const endMinutes = endHour * 60 + endMin

      if (startMinutes <= endMinutes) {
        return currentMinutes >= startMinutes && currentMinutes <= endMinutes
      } else {
        return currentMinutes >= startMinutes || currentMinutes <= endMinutes
      }
    } catch {
      return true
    }
  }, [timestampData.timeWindow])

  // Determine if we're in "Now" state
  const isNow = useMemo(() => {
    return isNowState(timestampData, status)
  }, [timestampData, status])

  // Calculate capture progress (0-100)
  const captureProgress = useMemo(() => {
    if (
      status !== "running" ||
      !timestampData.lastCapture ||
      !timestampData.nextCapture
    ) {
      return 0
    }

    try {
      const lastTime = new Date(timestampData.lastCapture).getTime()
      const nextTime = new Date(timestampData.nextCapture).getTime()
      const now = Date.now()

      if (now <= lastTime) return 0
      if (now >= nextTime) return 100

      const totalInterval = nextTime - lastTime
      const elapsed = now - lastTime
      const progress = Math.min(
        100,
        Math.max(0, (elapsed / totalInterval) * 100)
      )

      return Math.round(progress)
    } catch {
      return 0
    }
  }, [timestampData.lastCapture, timestampData.nextCapture, status])

  return {
    countdown,
    lastCaptureText,
    lastCaptureAbsolute,
    nextCaptureAbsolute,
    isOverdue,
    isWithinWindow,
    isNow,
    refreshInterval,
    captureProgress,
  }
}

/**
 * Simplified hook for just relative time formatting
 * Now uses centralized settings
 */
export function useRelativeTime(
  timestamp: string | null | undefined,
  options?: {
    includeAbsolute?: boolean
    refreshInterval?: number
  }
): string {
  const [relativeText, setRelativeText] = useState<string>("Never")
  const { timezone } = useTimezoneSettings()

  const refreshInterval = options?.refreshInterval || 30000 // 30 seconds default

  const updateText = useCallback(() => {
    const text = formatRelativeTime(timestamp, {
      includeAbsolute: options?.includeAbsolute || false,
      includeSeconds: true,
      timezone,
    })
    setRelativeText(text)
  }, [timestamp, options?.includeAbsolute, timezone])

  useEffect(() => {
    updateText()
    const timer = setInterval(updateText, refreshInterval)
    return () => clearInterval(timer)
  }, [updateText, refreshInterval])

  return relativeText
}
