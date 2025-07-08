/**
 * Frontend proxy for latest camera image full resolution serving
 *
 * Serves full resolution image for detailed viewing
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

    // Call the backend image serving endpoint
    const response = await fetch(
      `${fastApiUrl}/api/cameras/${cameraId}/latest-image/full`,
      {
        method: "GET",
        // Don't set Content-Type for image serving
      }
    )

    if (!response.ok) {
      if (response.status === 404) {
        return NextResponse.json(
          { error: "No images found for camera" },
          { status: 404 }
        )
      }

      const errorData = await response.text()
      return NextResponse.json(
        { error: `Backend error: ${response.status}`, details: errorData },
        { status: response.status }
      )
    }

    // Stream the image response
    const imageBuffer = await response.arrayBuffer()
    const contentType = response.headers.get("content-type") || "image/jpeg"

    return new NextResponse(imageBuffer, {
      status: 200,
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=60", // 1 minute cache for full images
        "Content-Length": imageBuffer.byteLength.toString(),
      },
    })
  } catch (error) {
    console.error("Latest image full proxy error:", error)
    return NextResponse.json(
      { error: "Failed to serve latest image full resolution" },
      { status: 500 }
    )
  }
}
