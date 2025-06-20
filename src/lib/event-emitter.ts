// src/lib/event-emitter.ts
// Global SSE event emitter for real-time updates

// SECURITY: Define allowed event types and their expected structure
const ALLOWED_EVENT_TYPES = [
  "connected",
  "image_captured",
  "camera_status_changed",
  "timelapse_status_changed",
  "camera_added",
  "camera_updated",
  "camera_deleted",
  "video_generated",
  "video_status_changed",
  "capture_now_requested",
  "thumbnail_regeneration_progress",
  "thumbnail_regeneration_complete",
  "thumbnail_regeneration_cancelled",
  "thumbnail_regeneration_error",
] as const

type AllowedEventType = (typeof ALLOWED_EVENT_TYPES)[number]

// SECURITY: Sanitize string values to prevent XSS
function sanitizeString(value: any): string {
  if (typeof value !== "string") {
    return String(value)
  }

  // Remove/escape HTML tags and script content
  return value
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;")
    .replace(/\//g, "&#x2F;")
    .slice(0, 1000) // Limit length
}

// SECURITY: Validate and sanitize event data
function sanitizeEventData(data: any): any {
  if (data === null || data === undefined) {
    return data
  }

  if (typeof data === "string") {
    return sanitizeString(data)
  }

  if (typeof data === "number" || typeof data === "boolean") {
    return data
  }

  if (Array.isArray(data)) {
    return data.map(sanitizeEventData).slice(0, 100) // Limit array size
  }

  if (typeof data === "object") {
    const sanitized: any = {}
    let keyCount = 0
    for (const [key, value] of Object.entries(data)) {
      if (keyCount >= 50) break // Limit object size
      const sanitizedKey = sanitizeString(key)
      sanitized[sanitizedKey] = sanitizeEventData(value)
      keyCount++
    }
    return sanitized
  }

  return String(data)
}

interface SSEEvent {
  type: AllowedEventType
  data: any
  timestamp: string
}

class EventEmitter {
  private clients: Set<ReadableStreamDefaultController> = new Set()

  addClient(controller: ReadableStreamDefaultController) {
    this.clients.add(controller)
  }

  removeClient(controller: ReadableStreamDefaultController) {
    this.clients.delete(controller)
  }

  getClientCount(): number {
    return this.clients.size
  }

  emit(event: SSEEvent) {
    const deadClients: ReadableStreamDefaultController[] = []

    this.clients.forEach((controller) => {
      try {
        const chunk = `data: ${JSON.stringify(event)}\n\n`
        controller.enqueue(new TextEncoder().encode(chunk))
      } catch (error) {
        console.error("❌ Failed to send SSE message:", error)
        deadClients.push(controller)
      }
    })

    // Clean up dead clients
    deadClients.forEach((client) => {
      this.removeClient(client)
    })

    if (deadClients.length > 0) {
      console.log(`🧹 Cleaned up ${deadClients.length} dead SSE clients`)
    }
  }
}

// Global event emitter instance
export const eventEmitter = new EventEmitter()

// Export types and utilities
export type { SSEEvent, AllowedEventType }
export { ALLOWED_EVENT_TYPES, sanitizeEventData }
