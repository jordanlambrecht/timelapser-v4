// src/lib/time-utils.ts
/**
 * Centralized time utility library for the Timelapser app
 * Handles all time formatting, countdown logic, and timezone conversions
 */

export interface TimeWindow {
  start: string // HH:MM:SS format
  end: string // HH:MM:SS format
  enabled: boolean
}

export interface CaptureTimestamp {
  lastCapture?: string | null
  nextCapture?: string | null
  captureInterval: number // seconds
  timeWindow?: TimeWindow
  timezone?: string // IANA timezone identifier (e.g., 'America/Chicago')
}

export interface RelativeTimeOptions {
  includeAbsolute?: boolean
  includeSeconds?: boolean
  shortFormat?: boolean
  timezone?: string
}

export interface CountdownOptions {
  showNowThreshold?: number // seconds (+/- this amount shows "now")
  showOverdue?: boolean
  shortFormat?: boolean
  timezone?: string
}

/**
 * Get the current configured timezone from settings
 * Falls back to browser timezone if not configured
 */
export function getConfiguredTimezone(providedTimezone?: string): string {
  if (providedTimezone) return providedTimezone
  
  // Try to get from browser's Intl API
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone
  } catch {
    return 'America/Chicago' // Default to Lincoln, NE timezone
  }
}

/**
 * Create a Date object in the specified timezone
 * This helps ensure consistent time calculations across the app
 */
export function createDateInTimezone(
  timestamp?: string | Date | null,
  timezone?: string
): Date {
  const tz = getConfiguredTimezone(timezone)
  
  if (!timestamp) {
    // Return current time in specified timezone
    return new Date()
  }
  
  if (typeof timestamp === 'string') {
    return new Date(timestamp)
  }
  
  return timestamp
}

/**
 * Format a date using the specified timezone
 */
export function formatDateInTimezone(
  date: Date,
  timezone?: string,
  options?: Intl.DateTimeFormatOptions
): string {
  const tz = getConfiguredTimezone(timezone)
  
  const defaultOptions: Intl.DateTimeFormatOptions = {
    timeZone: tz,
    month: "short",
    day: "numeric", 
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    ...options
  }
  
  try {
    return date.toLocaleDateString("en-US", defaultOptions)
  } catch {
    // Fallback to ISO string if timezone formatting fails
    return date.toISOString()
  }
}

/**
 * Format a duration in seconds to a human-readable string
 * @param duration - Duration in seconds (optional)
 * @returns Formatted duration string (e.g., "5m 30s", "45s", "Unknown")
 * @example
 * formatDuration(90) // "1m 30s"
 * formatDuration(45) // "45s"
 * formatDuration(undefined) // "Unknown"
 */
export const formatDuration = (duration?: number) => {
  if (!duration) return "Unknown"
  if (duration < 60) return `${duration}s`
  const minutes = Math.floor(duration / 60)
  const seconds = duration % 60
  return `${minutes}m ${seconds}s`
}

/**
 * Format a date string to a localized, human-readable format
 * @param dateString - ISO date string or any valid date string
 * @param timezone - Optional timezone override
 * @returns Formatted date string in specified timezone (e.g., "Jun 16, 2025, 03:30 PM")
 */
export const formatDate = (dateString: string, timezone?: string) => {
  const date = new Date(dateString)
  return formatDateInTimezone(date, timezone)
}

/**
 * Safely parse a timestamp string into a Date object
 * Handles timezone conversion by assuming database timestamps are UTC
 */
export function parseTimestamp(
  timestamp: string | null | undefined,
  timezone?: string
): Date | null {
  if (!timestamp) return null

  try {
    // If timestamp doesn't end with 'Z' and doesn't have timezone info, assume it's UTC
    let timestampStr = timestamp
    if (!timestamp.includes('Z') && !timestamp.includes('+') && !timestamp.includes('-', 10)) {
      // Add 'Z' to indicate UTC timezone
      timestampStr = timestamp + 'Z'
    }
    
    const date = new Date(timestampStr)
    if (isNaN(date.getTime())) return null
    return date
  } catch {
    return null
  }
}

/**
 * Check if a timestamp appears to be in the future (suspicious for "last capture")
 * This helps detect timezone misconfiguration
 */
export function isSuspiciousTimestamp(
  timestamp: string | null | undefined,
  type: 'last_capture' | 'next_capture' = 'last_capture'
): boolean {
  if (!timestamp) return false
  
  const date = parseTimestamp(timestamp)
  if (!date) return false
  
  const now = new Date()
  const diffInMs = date.getTime() - now.getTime()
  
  // Last capture should never be in the future (allow 30 second grace period for clock skew)
  if (type === 'last_capture') {
    return diffInMs > 30000
  }
  
  // Next capture should be in reasonable future (not more than 24 hours)
  if (type === 'next_capture') {
    return diffInMs > 24 * 60 * 60 * 1000 // 24 hours
  }
  
  return false
}

/**
 * Format a relative time string with optional absolute time
 * Examples: "5m ago", "2h ago, June 16th 2025 3:30pm", "Never"
 */
export function formatRelativeTime(
  timestamp: string | null | undefined,
  options: RelativeTimeOptions = {}
): string {
  const {
    includeAbsolute = false,
    includeSeconds = true,
    shortFormat = false,
    timezone,
  } = options

  if (!timestamp) return "Never"

  const date = parseTimestamp(timestamp)
  if (!date) return "Invalid time"

  // Get current time in the specified timezone
  const configuredTz = getConfiguredTimezone(timezone)
  let now: Date
  
  if (configuredTz === 'Etc/GMT' || configuredTz === 'GMT' || configuredTz === 'UTC') {
    // For GMT/UTC timezones, use actual UTC time
    now = new Date()
  } else {
    // For other timezones, convert current time to that timezone
    now = new Date()
  }

  const diffInMs = now.getTime() - date.getTime()
  const diffInSeconds = Math.floor(diffInMs / 1000)

  // Handle future timestamps (should not happen for "last capture")
  if (diffInSeconds < 0) {
    const futureSeconds = Math.abs(diffInSeconds)
    if (futureSeconds < 60 && includeSeconds) {
      return shortFormat
        ? `+${futureSeconds}s`
        : `In ${futureSeconds}s (future)`
    }
    const futureMinutes = Math.floor(futureSeconds / 60)
    return shortFormat ? `+${futureMinutes}m` : `In ${futureMinutes}m (future)`
  }

  // Calculate relative time
  let relativeText: string

  if (diffInSeconds < 5) {
    relativeText = "Just now"
  } else if (diffInSeconds < 60) {
    relativeText = includeSeconds ? `${diffInSeconds}s ago` : "< 1m ago"
  } else if (diffInSeconds < 3600) {
    const minutes = Math.floor(diffInSeconds / 60)
    relativeText = shortFormat ? `${minutes}m` : `${minutes}m ago`
  } else if (diffInSeconds < 86400) {
    const hours = Math.floor(diffInSeconds / 3600)
    relativeText = shortFormat ? `${hours}h` : `${hours}h ago`
  } else {
    const days = Math.floor(diffInSeconds / 86400)
    if (days === 1) {
      relativeText = shortFormat ? "1d" : "Yesterday"
    } else if (days < 7) {
      relativeText = shortFormat ? `${days}d` : `${days} days ago`
    } else if (days < 30) {
      const weeks = Math.floor(days / 7)
      relativeText = shortFormat
        ? `${weeks}w`
        : `${weeks} week${weeks > 1 ? "s" : ""} ago`
    } else {
      const months = Math.floor(days / 30)
      relativeText = shortFormat
        ? `${months}mo`
        : `${months} month${months > 1 ? "s" : ""} ago`
    }
  }

  // Add absolute time if requested
  if (includeAbsolute && diffInSeconds >= 3600) {
    // Only for times > 1 hour ago
    const absoluteText = formatAbsoluteTime(date, timezone)
    return `${relativeText}, ${absoluteText}`
  }

  return relativeText
}

/**
 * Format absolute time for display under counters
 * Shows date and time, year only if not current year
 * Example: "June 16th, 2025 13:35 (CDT)" or "June 16th 13:35 (UTC)"
 */
export function formatAbsoluteTimeForCounter(
  timestamp: string | null | undefined,
  timezone?: string
): string {
  if (!timestamp) return ""

  const date = parseTimestamp(timestamp)
  if (!date) return ""

  const configuredTz = getConfiguredTimezone(timezone)
  const currentYear = new Date().getFullYear()
  const timestampYear = date.getFullYear()
  
  // Get timezone abbreviation using Intl.DateTimeFormat
  let timezoneDisplay = "Local"
  try {
    if (configuredTz === 'Etc/GMT' || configuredTz === 'GMT' || configuredTz === 'UTC') {
      timezoneDisplay = "UTC"
    } else {
      // Use Intl to get the timezone abbreviation for this specific date
      const timezoneName = new Intl.DateTimeFormat('en-US', {
        timeZone: configuredTz,
        timeZoneName: 'short'
      }).formatToParts(date).find(part => part.type === 'timeZoneName')?.value
      
      timezoneDisplay = timezoneName || configuredTz.split('/').pop() || "Local"
    }
  } catch {
    // Fallback to last part of timezone name if Intl fails
    timezoneDisplay = configuredTz.split('/').pop() || "Local"
  }

  const options: Intl.DateTimeFormatOptions = {
    timeZone: configuredTz,
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }

  // Only include year if different from current year
  if (timestampYear !== currentYear) {
    options.year = "numeric"
  }

  try {
    const formattedDate = date.toLocaleDateString("en-US", options)
    return `${formattedDate} (${timezoneDisplay})`
  } catch {
    return date.toISOString()
  }
}

/**
 * Format an absolute time in a human-friendly format
 * Example: "June 16th 2025 3:30:02am"
 */
export function formatAbsoluteTime(
  date: Date | string | null | undefined,
  timezone?: string
): string {
  if (!date) return "Unknown"

  const dateObj = typeof date === "string" ? parseTimestamp(date, timezone) : date
  if (!dateObj) return "Invalid time"

  const options: Intl.DateTimeFormatOptions = {
    timeZone: getConfiguredTimezone(timezone),
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  }

  try {
    return dateObj.toLocaleDateString("en-US", options)
  } catch {
    return dateObj.toISOString()
  }
}

/**
 * Check if current time is within a time window
 * Uses specified timezone for time calculations
 */
export function isWithinTimeWindow(timeWindow?: TimeWindow, timezone?: string): boolean {
  if (!timeWindow?.enabled || !timeWindow.start || !timeWindow.end) {
    return true // No restrictions
  }

  try {
    const tz = getConfiguredTimezone(timezone)
    
    // Get current time in the specified timezone
    const now = new Date()
    const timeInTz = new Date(now.toLocaleString("en-US", { timeZone: tz }))
    const currentMinutes = timeInTz.getHours() * 60 + timeInTz.getMinutes()

    const [startHour, startMin] = timeWindow.start.split(":").map(Number)
    const [endHour, endMin] = timeWindow.end.split(":").map(Number)

    const startMinutes = startHour * 60 + startMin
    const endMinutes = endHour * 60 + endMin

    if (startMinutes <= endMinutes) {
      // Normal window (e.g., 06:00 - 18:00)
      return currentMinutes >= startMinutes && currentMinutes <= endMinutes
    } else {
      // Overnight window (e.g., 22:00 - 06:00)
      return currentMinutes >= startMinutes || currentMinutes <= endMinutes
    }
  } catch {
    return true // Default to allow if parsing fails
  }
}

/**
 * Calculate next capture time based on last capture and interval
 * This is a fallback when database next_capture_at is not available
 */
export function calculateNextCapture(
  lastCapture: string | null | undefined,
  captureInterval: number,
  timeWindow?: TimeWindow
): Date | null {
  if (!lastCapture) return null

  const lastDate = parseTimestamp(lastCapture)
  if (!lastDate) return null

  // Add interval to last capture
  let nextCapture = new Date(lastDate.getTime() + captureInterval * 1000)

  // If we have a time window, ensure next capture is within it
  if (timeWindow?.enabled && timeWindow.start && timeWindow.end) {
    // If next capture would be outside window, move it to next window start
    const nextDay = new Date(nextCapture)
    nextDay.setDate(nextDay.getDate() + 1)

    const [startHour, startMin] = timeWindow.start.split(":").map(Number)

    // Check if next capture is outside window
    if (!isWithinTimeWindow(timeWindow)) {
      // Move to next window start
      const windowStart = new Date(nextCapture)
      windowStart.setHours(startHour, startMin, 0, 0)

      // If window start is in the past, move to tomorrow
      if (windowStart <= new Date()) {
        windowStart.setDate(windowStart.getDate() + 1)
      }

      nextCapture = windowStart
    }
  }

  return nextCapture
}

/**
 * Check if a capture is overdue (past the expected time)
 */
export function isOverdue(
  nextCapture: string | null | undefined,
  graceSeconds: number = 60
): boolean {
  if (!nextCapture) return false

  const nextDate = parseTimestamp(nextCapture)
  if (!nextDate) return false

  const now = new Date()
  const overdueMs = now.getTime() - (nextDate.getTime() + graceSeconds * 1000)

  return overdueMs > 0
}

/**
 * Format a countdown to next capture with smart "now" detection
 * Examples: "5m 23s", "now", "overdue 2m", "paused"
 */
export function formatCountdown(
  data: CaptureTimestamp,
  status: "running" | "stopped" | "paused" = "running",
  options: CountdownOptions = {}
): string {
  const {
    showNowThreshold = 3, // seconds
    showOverdue = true,
    shortFormat = false,
    timezone,
  } = options

  // Handle non-running states
  if (status === "stopped") return shortFormat ? "Stopped" : "Stopped"
  if (status === "paused") return shortFormat ? "Paused" : "Paused"

  // Check time window
  const timeWindow = data.timeWindow
  if (timeWindow && !isWithinTimeWindow(timeWindow, timezone)) {
    return getTimeWindowMessage(timeWindow, shortFormat, timezone)
  }

  // Use database next_capture_at if available, otherwise calculate
  let nextCaptureTime: Date | null = null

  if (data.nextCapture) {
    nextCaptureTime = parseTimestamp(data.nextCapture)
  } else if (data.lastCapture) {
    nextCaptureTime = calculateNextCapture(
      data.lastCapture,
      data.captureInterval,
      timeWindow
    )
  }

  if (!nextCaptureTime) {
    return shortFormat ? "Due" : "First capture due"
  }

  // Get current time in the specified timezone
  const configuredTz = getConfiguredTimezone(timezone)
  let now: Date
  
  if (configuredTz === 'Etc/GMT' || configuredTz === 'GMT' || configuredTz === 'UTC') {
    // For GMT/UTC timezones, use actual UTC time
    now = new Date()
  } else {
    // For other timezones, convert current time to that timezone
    now = new Date()
  }

  const diffInMs = nextCaptureTime.getTime() - now.getTime()
  const diffInSeconds = Math.floor(diffInMs / 1000)

  // Check for "now" threshold
  if (Math.abs(diffInSeconds) <= showNowThreshold) {
    return "Now"
  }

  // Handle overdue
  if (diffInSeconds < 0 && showOverdue) {
    const overdueSeconds = Math.abs(diffInSeconds)
    if (overdueSeconds < 60) {
      return shortFormat ? `+${overdueSeconds}s` : `Overdue ${overdueSeconds}s`
    }
    const overdueMinutes = Math.floor(overdueSeconds / 60)
    const remainingSeconds = overdueSeconds % 60

    if (shortFormat) {
      return `+${overdueMinutes}m`
    }
    return remainingSeconds > 0
      ? `Overdue ${overdueMinutes}m ${remainingSeconds}s`
      : `Overdue ${overdueMinutes}m`
  }

  // Format future time - always show seconds when under 5 minutes
  if (diffInSeconds < 60) {
    return shortFormat ? `${diffInSeconds}s` : `${diffInSeconds}s`
  }

  const minutes = Math.floor(diffInSeconds / 60)
  const seconds = diffInSeconds % 60

  if (minutes < 5) {
    // Under 5 minutes: always show seconds for real-time updates
    if (shortFormat) {
      return `${minutes}m ${seconds}s`
    }
    return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`
  } else if (minutes < 60) {
    // 5+ minutes: show just minutes
    if (shortFormat) {
      return `${minutes}m`
    }
    return `${minutes}m`
  }

  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60

  if (shortFormat) {
    return `${hours}h`
  }
  return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`
}

/**
 * Get time window status message
 */
function getTimeWindowMessage(
  timeWindow: TimeWindow,
  shortFormat: boolean,
  timezone?: string
): string {
  if (!timeWindow.enabled || !timeWindow.start) return "Active"

  try {
    // Get current time in configured timezone
    const configuredTz = getConfiguredTimezone(timezone)
    let now: Date
    
    if (configuredTz === 'Etc/GMT' || configuredTz === 'GMT' || configuredTz === 'UTC') {
      now = new Date()
    } else {
      now = new Date()
    }

    const [startHour, startMin] = timeWindow.start.split(":").map(Number)

    // Calculate when the window will open next
    let windowStart = new Date(now)
    windowStart.setHours(startHour, startMin, 0, 0)

    // If start time has passed today, use tomorrow
    if (windowStart <= now) {
      windowStart.setDate(windowStart.getDate() + 1)
    }

    const timeUntilWindow = Math.floor(
      (windowStart.getTime() - now.getTime()) / 1000
    )

    if (timeUntilWindow < 3600) {
      // Less than 1 hour
      const minutes = Math.floor(timeUntilWindow / 60)
      return shortFormat ? `${minutes}m` : `Window opens in ${minutes}m`
    }

    const hours = Math.floor(timeUntilWindow / 3600)
    const minutes = Math.floor((timeUntilWindow % 3600) / 60)

    if (shortFormat) {
      return `${hours}h`
    }
    return minutes > 0
      ? `Window opens in ${hours}h ${minutes}m`
      : `Window opens in ${hours}h`
  } catch {
    return shortFormat ? "Snoozing" : "Outside window"
  }
}

/**
 * Get smart refresh interval based on countdown time
 * Returns milliseconds for setTimeout/setInterval
 */
export function getSmartRefreshInterval(
  data: CaptureTimestamp,
  status: "running" | "stopped" | "paused" = "running"
): number {
  // Don't refresh if stopped
  if (status === "stopped") return 60000 // 1 minute

  // Slow refresh if paused or outside window
  if (
    status === "paused" ||
    (data.timeWindow && !isWithinTimeWindow(data.timeWindow))
  ) {
    return 30000 // 30 seconds
  }

  // Get next capture time
  let nextCaptureTime: Date | null = null
  if (data.nextCapture) {
    nextCaptureTime = parseTimestamp(data.nextCapture)
  } else if (data.lastCapture) {
    nextCaptureTime = calculateNextCapture(
      data.lastCapture,
      data.captureInterval,
      data.timeWindow
    )
  }

  if (!nextCaptureTime) return 5000 // 5 seconds

  const now = new Date()
  const secondsUntilNext = Math.abs(Math.floor(
    (nextCaptureTime.getTime() - now.getTime()) / 1000
  ))

  // Ultra-fast refresh for "Now" state and immediate post-capture
  if (secondsUntilNext <= 3) return 500 // 0.5 seconds - for "Now" detection
  // Real-time per-second updates when under 5 minutes (300 seconds)
  if (secondsUntilNext <= 300) return 1000 // 1 second - for real-time countdown under 5 minutes
  // Moderate refresh for longer countdowns
  if (secondsUntilNext <= 600) return 5000 // 5 seconds - for 5-10 minute range
  // Slower refresh for distant times
  if (secondsUntilNext <= 1800) return 15000 // 15 seconds - for 10-30 minute range

  return 30000 // 30 seconds for very distant times
}

/**
 * Check if we're in the "Now" state for captures (within threshold of next capture)
 */
export function isNowState(
  data: CaptureTimestamp,
  status: "running" | "stopped" | "paused" = "running",
  threshold: number = 3
): boolean {
  if (status !== "running") return false

  // Get next capture time
  let nextCaptureTime: Date | null = null
  if (data.nextCapture) {
    nextCaptureTime = parseTimestamp(data.nextCapture)
  } else if (data.lastCapture) {
    nextCaptureTime = calculateNextCapture(
      data.lastCapture,
      data.captureInterval,
      data.timeWindow
    )
  }

  if (!nextCaptureTime) return false

  const now = new Date()
  const diffInSeconds = Math.abs(Math.floor(
    (nextCaptureTime.getTime() - now.getTime()) / 1000
  ))

  return diffInSeconds <= threshold
}

/**
 * Parse settings capture interval from various formats
 */
export function parseCaptureInterval(
  value: string | number | undefined
): number {
  if (typeof value === "number") return value
  if (typeof value === "string") {
    const parsed = parseInt(value, 10)
    return isNaN(parsed) ? 300 : parsed // Default 5 minutes
  }
  return 300 // Default 5 minutes
}

/**
 * React hook-compatible time formatter for relative times
 * Includes smart refresh logic
 */
export function useTimeFormatting() {
  return {
    formatRelativeTime,
    formatCountdown,
    formatAbsoluteTime,
    isWithinTimeWindow,
    isOverdue,
    getSmartRefreshInterval,
    parseCaptureInterval,
  }
}
