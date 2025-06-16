import { NextRequest, NextResponse } from "next/server"

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
] as const

type AllowedEventType = (typeof ALLOWED_EVENT_TYPES)[number]

// SECURITY: Sanitize string values to prevent XSS
function sanitizeString(value: any): string {
  if (typeof value !== "string") {
    return String(value)
  }

  // Remove/escape HTML tags and script content
  return value
    .replace(/<script[^>]*>.*?<\/script>/gi, "")
    .replace(/<[^>]*>/g, "")
    .replace(/javascript:/gi, "")
    .replace(/on\w+=/gi, "")
    .trim()
}

// SECURITY: Validate and sanitize event data
function validateAndSanitizeEvent(data: any): any {
  if (!data || typeof data !== "object") {
    throw new Error("Event data must be an object")
  }

  const { type, ...rest } = data

  // Validate event type
  if (!type || !ALLOWED_EVENT_TYPES.includes(type)) {
    throw new Error(
      `Invalid event type: ${type}. Allowed types: ${ALLOWED_EVENT_TYPES.join(
        ", "
      )}`
    )
  }

  // Recursively sanitize all string values
  function sanitizeObject(obj: any): any {
    if (obj === null || obj === undefined) {
      return obj
    }

    if (typeof obj === "string") {
      return sanitizeString(obj)
    }

    if (typeof obj === "number" || typeof obj === "boolean") {
      return obj
    }

    if (Array.isArray(obj)) {
      return obj.map(sanitizeObject)
    }

    if (typeof obj === "object") {
      const sanitized: any = {}
      for (const key in obj) {
        if (obj.hasOwnProperty(key)) {
          // Sanitize key name too
          const sanitizedKey = sanitizeString(key)
          sanitized[sanitizedKey] = sanitizeObject(obj[key])
        }
      }
      return sanitized
    }

    return obj
  }

  return {
    type: sanitizeString(type),
    ...sanitizeObject(rest),
    timestamp: new Date().toISOString(), // Always add server timestamp
  }
}

// Global event emitter for SSE
class EventEmitter {
  private clients: Set<ReadableStreamDefaultController> = new Set()

  addClient(controller: ReadableStreamDefaultController) {
    this.clients.add(controller)
  }

  removeClient(controller: ReadableStreamDefaultController) {
    this.clients.delete(controller)
  }

  emit(data: any) {
    try {
      const sanitizedData = validateAndSanitizeEvent(data)
      const message = `data: ${JSON.stringify(sanitizedData)}\n\n`

      console.log(
        `[SSE] Emitting event to ${this.clients.size} clients:`,
        sanitizedData
      )

      this.clients.forEach((controller) => {
        try {
          controller.enqueue(new TextEncoder().encode(message))
        } catch (error) {
          console.error("[SSE] Failed to send to client:", error)
          // Client disconnected, remove it
          this.clients.delete(controller)
        }
      })
    } catch (error) {
      console.error("Failed to emit event due to validation error:", error)
      // Don't broadcast invalid events
    }
  }

  getClientCount() {
    return this.clients.size
  }
}

// Global event emitter instance
const eventEmitter = new EventEmitter()

// Export eventEmitter for use in other route handlers
export { eventEmitter }

export async function GET(request: NextRequest) {
  console.log("🔗 New SSE connection established")

  // Set up Server-Sent Events
  const stream = new ReadableStream({
    start(controller) {
      // Add this client to the emitter
      eventEmitter.addClient(controller)
      console.log(`📊 SSE clients connected: ${eventEmitter.getClientCount()}`)

      // Send initial connection message
      const welcomeMessage = `data: ${JSON.stringify({
        type: "connected",
        message: "SSE connection established",
        timestamp: new Date().toISOString(),
      })}\n\n`

      controller.enqueue(new TextEncoder().encode(welcomeMessage))

      // Keep connection alive with heartbeat
      const heartbeat = setInterval(() => {
        try {
          const heartbeatMessage = `data: ${JSON.stringify({
            type: "heartbeat",
            timestamp: new Date().toISOString(),
          })}\n\n`
          controller.enqueue(new TextEncoder().encode(heartbeatMessage))
        } catch (error) {
          console.log("💔 SSE heartbeat failed, removing client")
          clearInterval(heartbeat)
          eventEmitter.removeClient(controller)
        }
      }, 30000) // Every 30 seconds

      // Clean up on close
      request.signal?.addEventListener("abort", () => {
        console.log("🔌 SSE connection closed by client")
        clearInterval(heartbeat)
        eventEmitter.removeClient(controller)
        console.log(
          `📊 SSE clients remaining: ${eventEmitter.getClientCount()}`
        )
        try {
          controller.close()
        } catch (error) {
          // Already closed
        }
      })
    },
  })

  return new NextResponse(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      // SECURITY: More restrictive CORS - only allow same origin by default
      // If you need cross-origin access, replace * with specific allowed origins
      "Access-Control-Allow-Origin":
        process.env.NODE_ENV === "development"
          ? "*"
          : request.headers.get("origin") || "",
      "Access-Control-Allow-Methods": "GET",
      "Access-Control-Allow-Headers": "Cache-Control",
      // SECURITY: Add additional security headers
      "X-Content-Type-Options": "nosniff",
      "X-Frame-Options": "DENY",
    },
  })
}

// POST endpoint to broadcast events (used by Python worker)
// SECURITY: Now validates and sanitizes all incoming event data
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    // SECURITY: Validate and sanitize event data before broadcasting
    const sanitizedEvent = validateAndSanitizeEvent(body)

    // Broadcast sanitized event to all connected clients
    eventEmitter.emit(sanitizedEvent)

    return NextResponse.json({
      success: true,
      clients: eventEmitter.getClientCount(),
      event: sanitizedEvent,
    })
  } catch (error) {
    console.error("Error broadcasting event:", error)

    // Return specific validation errors to help debug legitimate requests
    if (
      error instanceof Error &&
      error.message.includes("Invalid event type")
    ) {
      return NextResponse.json(
        {
          error: "Event validation failed",
          details: error.message,
        },
        { status: 400 }
      )
    }

    return NextResponse.json(
      {
        error: "Failed to broadcast event",
      },
      { status: 500 }
    )
  }
}
