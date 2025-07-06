// src/app/api/cameras/[id]/capture/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"
import { eventEmitter } from "@/lib/event-emitter"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    
    // Proxy to FastAPI backend manual capture endpoint
    const response = await proxyToFastAPI(`/api/cameras/${id}/capture-now`, {
      method: "POST",
    })

    // If successful, broadcast capture event
    if (response.status === 200) {
      const responseText = await response.text()
      const responseData = responseText ? JSON.parse(responseText) : {}

      // Broadcast manual capture event
      eventEmitter.emit({
        type: "manual_capture_completed",
        data: {
          camera_id: parseInt(id),
          capture_result: responseData,
        },
        timestamp: new Date().toISOString(),
      })

      return NextResponse.json(responseData, { status: response.status })
    }

    return response
  } catch (error) {
    console.error("Manual capture error:", error)
    return NextResponse.json(
      { error: "Failed to trigger manual capture" },
      { status: 500 }
    )
  }
}
