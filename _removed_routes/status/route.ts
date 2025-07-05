// src/app/api/timelapses/[id]/status/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

// Import eventEmitter for broadcasting changes
import { eventEmitter } from "@/lib/event-emitter"

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const timelapseId = id

  try {
    const body = await request.json()

    // Proxy to FastAPI backend's entity-based endpoint
    const response = await proxyToFastAPI(
      `/api/timelapses/${timelapseId}/status`,
      {
        method: "PUT",
        body,
      }
    )

    // Parse the response
    const responseData = await response.json()

    // If successful, broadcast the event
    if (response.status === 200 || response.status === 201) {
      // We need to get the camera_id for the event - it might be in query params or we need to fetch it
      // Let's check if camera_id is provided in the request body or query params
      const { searchParams } = new URL(request.url)
      const cameraId = searchParams.get("camera_id") || body.camera_id

      if (cameraId) {
        // Broadcast timelapse status changed event
        eventEmitter.emit({
          type: "timelapse_status_changed",
          data: {
            camera_id: parseInt(cameraId),
            timelapse_id: parseInt(timelapseId),
            status: body.status,
          },
          timestamp: new Date().toISOString(),
        })

        // Also broadcast camera status change to refresh UI
        eventEmitter.emit({
          type: "camera_status_changed",
          data: {
            camera_id: parseInt(cameraId),
            status: body.status === "running" ? "active" : "inactive",
          },
          timestamp: new Date().toISOString(),
        })
      } else {
        // If no camera_id provided, we need to fetch it from the timelapse
        // This is a fallback but we should try to provide camera_id in the request
        console.warn(
          `No camera_id provided for timelapse ${timelapseId} status update`
        )
      }

      console.log(
        `Timelapse ${timelapseId} status updated successfully:`,
        responseData
      )
      return NextResponse.json(responseData, { status: response.status })
    } else {
      console.error(
        `Failed to update timelapse ${timelapseId} status:`,
        responseData
      )
      return NextResponse.json(responseData, { status: response.status })
    }
  } catch (error) {
    console.error(`Error updating timelapse ${timelapseId} status:`, error)
    return NextResponse.json(
      {
        error: "Failed to update timelapse status",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    )
  }
}
