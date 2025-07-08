/**
 * Frontend proxy for latest camera image download
 *
 * Downloads latest image with proper filename (e.g., "Camera1_day5_20250630_143022.jpg")
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

    // Call the backend download endpoint
    const response = await fetch(
      `${fastApiUrl}/api/cameras/${cameraId}/latest-image/download`,
      {
        method: "GET",
        // Don't set Content-Type for file download
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

    // Stream the download response with proper headers
    const imageBuffer = await response.arrayBuffer()
    const contentType = response.headers.get("content-type") || "image/jpeg"
    const contentDisposition =
      response.headers.get("content-disposition") || "attachment"

    return new NextResponse(imageBuffer, {
      status: 200,
      headers: {
        "Content-Type": contentType,
        "Content-Disposition": contentDisposition,
        "Content-Length": imageBuffer.byteLength.toString(),
        "Cache-Control": "no-cache", // Don't cache downloads
      },
    })
  } catch (error) {
    console.error("Latest image download proxy error:", error)
    return NextResponse.json(
      { error: "Failed to download latest image" },
      { status: 500 }
    )
  }
}
