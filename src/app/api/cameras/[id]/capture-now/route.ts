// src/app/api/cameras/[id]/capture-now/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

// Import eventEmitter for broadcasting changes
import { eventEmitter } from "@/app/api/events/route"

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const cameraId = params.id
    
    console.log(`Triggering immediate capture for camera ${cameraId}`)

    // Proxy to FastAPI backend
    const response = await proxyToFastAPI(`/api/cameras/${cameraId}/capture-now`, {
      method: "POST",
    })

    const responseData = await response.json()
    
    // If successful, broadcast capture event
    if (response.status === 200) {
      console.log("Broadcasting capture_now_requested event:", {
        camera_id: parseInt(cameraId),
        timestamp: new Date().toISOString(),
      })
      
      eventEmitter.emit({
        type: "capture_now_requested",
        camera_id: parseInt(cameraId),
        timestamp: new Date().toISOString(),
      })
    }
    
    return NextResponse.json(responseData, { status: response.status })
  } catch (error) {
    console.error(`Error triggering capture for camera ${params.id}:`, error)
    return NextResponse.json(
      { error: "Failed to trigger capture" },
      { status: 500 }
    )
  }
}
