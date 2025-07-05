/**
 * Frontend proxy for unified latest camera image metadata endpoint
 *
 * NEW UNIFIED ENDPOINT - Returns complete metadata + URLs for all image variants
 * Replaces multiple separate API calls with single comprehensive response
 */

import { NextRequest, NextResponse } from "next/server"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const cameraId = (await params).id
    const fastApiUrl = process.env.NEXT_PUBLIC_FASTAPI_URL

    if (!fastApiUrl) {
      return NextResponse.json(
        { error: "FastAPI URL not configured" },
        { status: 500 }
      )
    }

    // Call the new unified backend endpoint
    const response = await fetch(
      `${fastApiUrl}/api/cameras/${cameraId}/latest-image`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      }
    )

    if (!response.ok) {
      const errorData = await response.text()
      return NextResponse.json(
        { error: `Backend error: ${response.status}`, details: errorData },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("Latest image metadata proxy error:", error)
    return NextResponse.json(
      { error: "Failed to fetch latest image metadata" },
      { status: 500 }
    )
  }
}
