// src/app/api/video-automation/timelapse/[id]/settings/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPIWithQuery, proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const { searchParams } = new URL(request.url)

  try {
    // Proxy to FastAPI backend with query parameters
    return await proxyToFastAPIWithQuery(`/api/video-automation/timelapse/${id}/settings`, searchParams)
  } catch (error) {
    console.error("Failed to fetch timelapse automation settings:", error)
    return NextResponse.json(
      { error: "Failed to fetch timelapse automation settings" },
      { status: 500 }
    )
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params

  try {
    const body = await request.json()

    // Proxy to FastAPI backend
    return await proxyToFastAPI(`/api/video-automation/timelapse/${id}/settings`, {
      method: "PUT",
      body,
    })
  } catch (error) {
    console.error("Failed to update timelapse automation settings:", error)
    return NextResponse.json(
      { error: "Failed to update timelapse automation settings" },
      { status: 500 }
    )
  }
}
