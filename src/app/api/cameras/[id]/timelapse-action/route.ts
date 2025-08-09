import { NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"
import { eventEmitter } from "@/lib/event-emitter"

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const body = await request.json().catch(() => ({}))

    // Use standardized proxy utility
    const response = await proxyToFastAPI(
      `/api/cameras/${id}/timelapse-action`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      }
    )

    // If successful, broadcast the event for real-time updates
    if (response.ok) {
      const data = await response.json()
      const cameraId = parseInt(id)

      // Broadcast specific action events that the frontend expects
      const eventData = {
        camera_id: cameraId,
        action: body.action,
        status: data.timelapse_status || data.status,
        timelapse_id: data.timelapse_id,
        ...data.data, // Include any additional data from backend
      }

      // Emit specific events based on action type for proper frontend handling
      switch (body.action) {
        case "create":
          eventEmitter.emit({
            type: "timelapse_started",
            data: eventData,
            timestamp: new Date().toISOString(),
          })
          break
        case "pause":
          eventEmitter.emit({
            type: "timelapse_paused", 
            data: eventData,
            timestamp: new Date().toISOString(),
          })
          break
        case "resume":
          eventEmitter.emit({
            type: "timelapse_resumed",
            data: eventData,
            timestamp: new Date().toISOString(),
          })
          break
        case "end":
          eventEmitter.emit({
            type: "timelapse_stopped",
            data: eventData,
            timestamp: new Date().toISOString(),
          })
          break
      }

      // Also emit general status changed event for compatibility
      eventEmitter.emit({
        type: "timelapse_status_changed",
        data: eventData,
        timestamp: new Date().toISOString(),
      })

      return NextResponse.json(data)
    }

    // Handle error response
    const errorData = await response.json().catch(() => ({
      message: "Unknown error",
    }))
    return NextResponse.json(
      { error: errorData.message || "Failed to execute timelapse action" },
      { status: response.status }
    )
  } catch (error) {
    console.error("Error executing timelapse action:", error)
    return NextResponse.json(
      { error: "Failed to execute timelapse action" },
      { status: 500 }
    )
  }
}
