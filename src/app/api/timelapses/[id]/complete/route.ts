// src/app/api/timelapses/[id]/complete/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"
import { eventEmitter } from "@/lib/event-emitter"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: timelapseId } = await params
    const url = new URL(request.url)
    const cameraId = url.searchParams.get("camera_id")

    // Proxy to FastAPI backend
    const backendUrl = `/api/timelapses/${timelapseId}/complete${
      cameraId ? `?camera_id=${cameraId}` : ""
    }`
    const response = await proxyToFastAPI(backendUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    })

    // If successful, broadcast the event
    if (response.status === 200 || response.status === 201) {
      const responseData = await response.json()

      // Broadcast timelapse status changed event
      console.log("Broadcasting timelapse completed event:", {
        camera_id: cameraId ? parseInt(cameraId) : null,
        timelapse_id: parseInt(timelapseId),
        status: "completed",
      })

      eventEmitter.emit({
        type: "timelapse_status_changed",
        data: {
          camera_id: cameraId ? parseInt(cameraId) : null,
          timelapse_id: parseInt(timelapseId),
          status: "completed",
        },
        timestamp: new Date().toISOString(),
      })

      // Also broadcast camera status change to refresh UI
      if (cameraId) {
        eventEmitter.emit({
          type: "camera_status_changed",
          data: {
            camera_id: parseInt(cameraId),
            status: "inactive",
          },
          timestamp: new Date().toISOString(),
        })
      }

      return NextResponse.json(responseData, { status: response.status })
    }

    return response
  } catch (error) {
    console.error("Timelapse completion error:", error)
    return NextResponse.json(
      { error: "Failed to complete timelapse" },
      { status: 500 }
    )
  }
}
