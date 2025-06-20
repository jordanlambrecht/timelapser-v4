import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

// 🎯 COMPREHENSIVE CAMERA DETAILS ENDPOINT
// Single endpoint that replaces 6 separate API calls with one optimized request
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const cameraId = parseInt(id)
    
    if (isNaN(cameraId) || cameraId <= 0) {
      return NextResponse.json(
        { error: "Invalid camera ID" },
        { status: 400 }
      )
    }

    console.log(`[API] Fetching comprehensive camera details for camera ${cameraId}`)

    // 🎯 SIMPLIFIED: Direct proxy return like other routes
    return proxyToFastAPI(`/api/cameras/${cameraId}/details`)

  } catch (error) {
    console.error("[API] Error in comprehensive camera details endpoint:", error)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}
