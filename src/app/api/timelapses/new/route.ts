// src/app/api/timelapses/new/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

// Import eventEmitter for broadcasting changes
import { eventEmitter } from "@/lib/event-emitter"

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    // Proxy to FastAPI backend's new entity-based endpoint
    const response = await proxyToFastAPI("/api/timelapses/new", {
      method: "POST",
      body,
    })

    // Parse the response
    const responseData = await response.json()

    // If successful, broadcast the event
    if (response.status === 200 || response.status === 201) {
      // Broadcast timelapse status changed event
      eventEmitter.emit({
        type: "timelapse_status_changed",
        data: {
          camera_id: body.camera_id,
          timelapse_id: responseData.timelapse_id,
          status: "running",
        },
        timestamp: new Date().toISOString(),
      })

      // Also broadcast camera status change to refresh UI
      eventEmitter.emit({
        type: "camera_status_changed",
        data: {
          camera_id: body.camera_id,
          status: "active",
        },
        timestamp: new Date().toISOString(),
      })

      console.log(
        "New entity-based timelapse created successfully:",
        responseData
      )
      return NextResponse.json(responseData, { status: response.status })
    } else {
      console.error("Failed to create new timelapse:", responseData)
      return NextResponse.json(responseData, { status: response.status })
    }
  } catch (error) {
    console.error("Error creating new timelapse:", error)
    return NextResponse.json(
      {
        error: "Failed to create new timelapse",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    )
  }
}
