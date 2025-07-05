// src/app/api/timelapses/[id]/pause/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"
import { eventEmitter } from "@/lib/event-emitter"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: timelapseId } = await params

    // Proxy to FastAPI backend
    const backendUrl = `/api/timelapses/${timelapseId}/pause`
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
      console.log("Broadcasting timelapse paused event:", {
        timelapse_id: parseInt(timelapseId),
        status: "paused",
      })

      eventEmitter.emit({
        type: "timelapse_status_changed",
        data: {
          camera_id: responseData.camera_id || null,
          timelapse_id: parseInt(timelapseId),
          status: "paused",
        },
        timestamp: new Date().toISOString(),
      })

      // Also broadcast camera status change to refresh UI
      if (responseData.camera_id) {
        eventEmitter.emit({
          type: "camera_status_changed",
          data: {
            camera_id: responseData.camera_id,
            status: "inactive",
          },
          timestamp: new Date().toISOString(),
        })
      }

      return NextResponse.json(responseData, { status: response.status })
    }

    return response
  } catch (error) {
    console.error("Timelapse pause error:", error)
    return NextResponse.json(
      { error: "Failed to pause timelapse" },
      { status: 500 }
    )
  }
}