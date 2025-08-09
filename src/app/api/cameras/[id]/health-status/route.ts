import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"
import { eventEmitter } from "@/lib/event-emitter"

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const body = await request.json()

    // Proxy the health status update to FastAPI backend
    const response = await proxyToFastAPI(`/api/cameras/${id}/health-status`, {
      method: "PATCH",
      body,
    })

    // If successful, broadcast the camera status changed event
    if (response.ok) {
      const responseData = await response.json()

      // Broadcast camera status changed event for real-time UI updates
      eventEmitter.emit({
        type: "camera_status_changed",
        data: {
          camera_id: parseInt(id),
          health_status: body.health_status || responseData.health_status,
          status: responseData.status,
          consecutive_failures: responseData.consecutive_failures,
          last_seen: responseData.last_seen,
        },
        timestamp: new Date().toISOString(),
      })

      return NextResponse.json(responseData)
    }

    // Handle error response
    const errorData = await response.json().catch(() => ({
      message: "Unknown error",
    }))
    return NextResponse.json(
      { error: errorData.message || "Failed to update camera health status" },
      { status: response.status }
    )
  } catch (error) {
    console.error("Error updating camera health status:", error)
    return NextResponse.json(
      { error: "Failed to update camera health status" },
      { status: 500 }
    )
  }
}