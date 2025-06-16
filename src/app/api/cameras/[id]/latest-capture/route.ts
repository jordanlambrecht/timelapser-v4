import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const cameraId = parseInt(id)

  if (isNaN(cameraId)) {
    return NextResponse.json({ error: "Invalid camera ID" }, { status: 400 })
  }

  // Proxy the request to FastAPI backend
  return proxyToFastAPI(`/api/cameras/${cameraId}/latest-capture`)
}
