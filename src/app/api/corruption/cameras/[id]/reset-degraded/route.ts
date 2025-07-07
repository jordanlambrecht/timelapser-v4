// src/app/api/corruption/cameras/[id]/reset-degraded/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

// Import eventEmitter for broadcasting changes
import { eventEmitter } from "@/lib/event-emitter"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params

  try {
    const cameraId = parseInt(id)
    if (isNaN(cameraId)) {
      return NextResponse.json(
        { error: "Invalid camera ID" },
        { status: 400 }
      )
    }

    // Proxy to FastAPI backend
    const response = await proxyToFastAPI(`/api/corruption/camera/${cameraId}/reset-degraded`, {
      method: "POST",
    })

    if (!response.ok) {
      const errorData = await response.json()
      return NextResponse.json(
        { error: errorData.detail || "Failed to reset camera degraded mode" },
        { status: response.status }
      )
    }

    const data = await response.json()

    // Broadcast SSE event for real-time updates
    eventEmitter.emit({
      type: "camera_corruption_reset",
      data: {
        camera_id: cameraId,
        degraded_mode_active: false,
        consecutive_corruption_failures: 0,
      },
      timestamp: new Date().toISOString(),
    })

    return NextResponse.json(data)
  } catch (error) {
    console.error("Failed to reset camera degraded mode:", error)
    return NextResponse.json(
      {
        error: "Failed to reset camera degraded mode",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    )
  }
}
