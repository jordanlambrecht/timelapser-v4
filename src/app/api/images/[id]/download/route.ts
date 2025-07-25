// src/app/api/images/[id]/download/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPIWithQuery } from "@/lib/fastapi-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const imageId = parseInt(id)

    // Validate image ID
    if (isNaN(imageId) || imageId <= 0) {
      return NextResponse.json({ error: "Invalid image ID" }, { status: 400 })
    }

    // Pass through size query parameter with validation
    const searchParams = request.nextUrl.searchParams
    const size = searchParams.get("size") || "full"

    // Validate size parameter against known values
    const validSizes = ["full", "small", "thumbnail"]
    if (!validSizes.includes(size)) {
      return NextResponse.json(
        { error: "Invalid size parameter. Must be: full, small, or thumbnail" },
        { status: 400 }
      )
    }

    return proxyToFastAPIWithQuery(`/api/images/${imageId}/serve`, searchParams)
  } catch (error) {
    console.error("Image download proxy error:", error)
    return NextResponse.json(
      { error: "Failed to download image" },
      { status: 500 }
    )
  }
}
