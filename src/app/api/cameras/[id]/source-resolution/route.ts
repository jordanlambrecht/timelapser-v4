// src/app/api/cameras/[id]/source-resolution/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params

  try {
    const cameraId = parseInt(id)
    if (isNaN(cameraId)) {
      return NextResponse.json({ error: "Invalid camera ID" }, { status: 400 })
    }

    // Proxy to FastAPI backend
    return await proxyToFastAPI(`/api/cameras/${cameraId}/source-resolution`, {
      method: "GET",
    })
  } catch (error) {
    console.error("Failed to get camera source resolution:", error)
    return NextResponse.json(
      { error: "Failed to get camera source resolution" },
      { status: 500 }
    )
  }
}
