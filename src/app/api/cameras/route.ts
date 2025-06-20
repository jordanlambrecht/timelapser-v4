// src/app/api/cameras/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

// Import eventEmitter for broadcasting changes
import { eventEmitter } from "@/lib/event-emitter"

export async function GET() {
  // Proxy to FastAPI backend
  return proxyToFastAPI("/api/cameras")
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    // Proxy to FastAPI backend
    const response = await proxyToFastAPI("/api/cameras", {
      method: "POST",
      body,
    })

    // If successful, broadcast the event
    if (response.status === 200 || response.status === 201) {
      // Get the response data from the response body
      const responseText = await response.text()
      const responseData = responseText ? JSON.parse(responseText) : {}

      // Broadcast camera added event
      eventEmitter.emit({
        type: "camera_added",
        data: {
          camera: responseData,
        },
        timestamp: new Date().toISOString(),
      })

      // Return the response data
      return NextResponse.json(responseData, { status: response.status })
    }

    return response
  } catch (error) {
    console.error("Camera creation error:", error)
    return NextResponse.json(
      { error: "Failed to create camera" },
      { status: 500 }
    )
  }
}
