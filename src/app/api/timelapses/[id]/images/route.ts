// src/app/api/timelapses/[id]/images/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params

  try {
    // Extract query parameters
    const { searchParams } = new URL(request.url)
    const page = searchParams.get('page') || '1'
    const per_page = searchParams.get('per_page') || '50'
    const search = searchParams.get('search') || ''

    // Build query string for FastAPI
    const queryParams = new URLSearchParams({
      page,
      per_page,
      ...(search && { search }),
    })

    // Proxy to FastAPI backend
    const response = await proxyToFastAPI(`/api/timelapses/${id}/images?${queryParams}`)

    if (!response.ok) {
      return NextResponse.json(
        { error: "Failed to fetch timelapse images" },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("Failed to fetch timelapse images:", error)
    return NextResponse.json(
      { error: "Failed to fetch timelapse images" },
      { status: 500 }
    )
  }
}
