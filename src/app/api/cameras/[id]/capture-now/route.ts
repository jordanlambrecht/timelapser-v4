// src/app/api/cameras/[id]/capture-now/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

// Import eventEmitter for broadcasting changes
import { eventEmitter } from "@/lib/event-emitter"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const cameraId = id

  try {
    // Proxy to FastAPI backend
    const response = await proxyToFastAPI(
      `/api/cameras/${cameraId}/capture-now`,
      {
        method: "POST",
      }
    )

    const responseData = await response.json()

    // If successful, broadcast capture event
    if (response.status === 200) {
      eventEmitter.emit({
        type: "capture_now_requested",
        data: {
          camera_id: parseInt(cameraId),
        },
        timestamp: new Date().toISOString(),
      })
    }

    return NextResponse.json(responseData, { status: response.status })
  } catch (error) {
    console.error(`Error triggering capture for camera ${cameraId}:`, error)
    return NextResponse.json(
      { error: "Failed to trigger capture" },
      { status: 500 }
    )
  }
}
