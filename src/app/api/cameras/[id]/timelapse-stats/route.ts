// src/app/api/cameras/[id]/timelapse-stats/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const cameraId = id

  try {
    console.log(`Fetching timelapse stats for camera ${cameraId}`)

    // Proxy to FastAPI backend
    const response = await proxyToFastAPI(
      `/api/cameras/${cameraId}/timelapse-stats`,
      {
        method: "GET",
      }
    )

    const responseData = await response.json()

    console.log(`Timelapse stats for camera ${cameraId}:`, responseData)

    return NextResponse.json(responseData, { status: response.status })
  } catch (error) {
    console.error(
      `Error fetching timelapse stats for camera ${cameraId}:`,
      error
    )
    return NextResponse.json(
      { error: "Failed to fetch timelapse statistics" },
      { status: 500 }
    )
  }
}
