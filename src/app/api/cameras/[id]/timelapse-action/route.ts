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

      // Broadcast timelapse status changed event
      eventEmitter.emit({
        type: "timelapse_status_changed",
        data: {
          camera_id: parseInt(id),
          action: body.action,
          status: data.status,
          timelapse_id: data.timelapse_id,
        },
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
