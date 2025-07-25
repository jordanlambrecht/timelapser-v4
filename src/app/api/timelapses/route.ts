// src/app/api/timelapses/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI, proxyToFastAPIWithQuery } from "@/lib/fastapi-proxy"

// Import eventEmitter for broadcasting changes
import { eventEmitter } from "@/lib/event-emitter"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)

  // Proxy to FastAPI backend with query parameters
  return proxyToFastAPIWithQuery("/api/timelapses", searchParams)
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { searchParams } = new URL(request.url)
    const cameraId = searchParams.get("camera_id")

    // Determine if this is creating a new timelapse or updating existing one
    const isNewTimelapse = !body.timelapse_id && cameraId
    const isStatusUpdate = body.timelapse_id && body.status

    let response: Response
    let fastApiEndpoint: string

    if (isNewTimelapse) {
      // Creating a new comprehensive timelapse - use full timelapse endpoint with camera_id
      fastApiEndpoint = `/api/timelapses?camera_id=${cameraId}`

      // Add camera_id to the body for backend validation
      const timelapseData = {
        ...body,
        camera_id: parseInt(cameraId),
      }

      response = await proxyToFastAPI(fastApiEndpoint, {
        method: "POST",
        body: timelapseData,
      })
    } else if (isStatusUpdate) {
      // Updating status of existing timelapse - use main timelapse endpoint
      fastApiEndpoint = `/api/timelapses/${body.timelapse_id}`
      response = await proxyToFastAPI(fastApiEndpoint, {
        method: "PUT",
        body: { status: body.status },
      })
    } else {
      // Fallback to legacy endpoint for other cases
      fastApiEndpoint = "/api/timelapses"
      response = await proxyToFastAPI(fastApiEndpoint, {
        method: "POST",
        body,
      })
    }

    // If successful, broadcast the event
    if (response.status === 200 || response.status === 201) {
      const responseData = await response.json()

      // Broadcast timelapse status changed event
      eventEmitter.emit({
        type: "timelapse_status_changed",
        data: {
          camera_id: body.camera_id,
          timelapse_id: responseData.timelapse_id,
          status: body.status,
        },
        timestamp: new Date().toISOString(),
      })

      // Return the response data
      return NextResponse.json(responseData, { status: response.status })
    }

    return response
  } catch (error) {
    console.error("Timelapse operation error:", error)
    return NextResponse.json(
      { error: "Failed to update timelapse" },
      { status: 500 }
    )
  }
}
