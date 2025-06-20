// src/app/api/timelapses/[id]/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params

  try {
    // Proxy to FastAPI backend
    const response = await proxyToFastAPI(`/api/timelapses/${id}`)

    if (!response.ok) {
      return NextResponse.json(
        { error: "Timelapse not found" },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("Failed to fetch timelapse:", error)
    return NextResponse.json(
      { error: "Failed to fetch timelapse" },
      { status: 500 }
    )
  }
}
