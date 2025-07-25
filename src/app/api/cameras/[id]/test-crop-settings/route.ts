// src/app/api/cameras/[id]/test-crop-settings/route.ts
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

    const body = await request.json()

    // Proxy to FastAPI backend
    return await proxyToFastAPI(`/api/cameras/${cameraId}/test-crop-settings`, {
      method: "POST",
      body,
    })
  } catch (error) {
    console.error("Failed to test camera crop settings:", error)
    return NextResponse.json(
      { error: "Failed to test camera crop settings" },
      { status: 500 }
    )
  }
}
