import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI, proxyToFastAPIWithQuery } from "@/lib/fastapi-proxy"

// Import eventEmitter for broadcasting changes
import { eventEmitter } from "@/app/api/events/route"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)

  // Proxy to FastAPI backend with query parameters
  return proxyToFastAPIWithQuery("/api/timelapses", searchParams)
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    // Proxy to FastAPI backend
    const response = await proxyToFastAPI("/api/timelapses", {
      method: "POST",
      body,
    })

    // If successful, broadcast the event
    if (response.status === 200 || response.status === 201) {
      const responseData = await response.json()

      // Broadcast timelapse status changed event
      console.log("Broadcasting timelapse_status_changed event:", {
        camera_id: body.camera_id,
        timelapse_id: responseData.timelapse_id,
        status: body.status,
      })
      eventEmitter.emit({
        type: "timelapse_status_changed",
        camera_id: body.camera_id,
        timelapse_id: responseData.timelapse_id,
        status: body.status,
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
