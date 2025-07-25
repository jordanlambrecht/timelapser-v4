// src/app/api/cameras/[id]/detect-resolution/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function POST(
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
    return await proxyToFastAPI(`/api/cameras/${cameraId}/detect-resolution`, {
      method: "POST",
    })
  } catch (error) {
    console.error("Failed to detect camera source resolution:", error)
    return NextResponse.json(
      { error: "Failed to detect camera source resolution" },
      { status: 500 }
    )
  }
}
