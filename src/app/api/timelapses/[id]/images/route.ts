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
    const page = parseInt(searchParams.get('page') || '1')
    const per_page = parseInt(searchParams.get('per_page') || '50')
    const search = searchParams.get('search') || ''

    // Convert page/per_page to limit/offset for FastAPI
    const limit = per_page
    const offset = (page - 1) * per_page

    // Build query string for FastAPI
    const queryParams = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
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
