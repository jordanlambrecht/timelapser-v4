// src/app/api/cameras/[id]/status/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"
import { eventEmitter } from "@/lib/event-emitter"

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const body = await request.json()
    
    const response = await proxyToFastAPI(`/api/cameras/${id}/status`, {
      method: "PUT",
      body,
    })

    // Broadcast status update event
    if (response.status === 200) {
      eventEmitter.emit({
        type: "camera_status_updated",
        data: {
          camera_id: parseInt(id),
          status: body.status,
        },
        timestamp: new Date().toISOString(),
      })
    }

    return response
  } catch (error) {
    console.error("Camera status update error:", error)
    return NextResponse.json(
      { error: "Failed to update camera status" },
      { status: 500 }
    )
  }
}
