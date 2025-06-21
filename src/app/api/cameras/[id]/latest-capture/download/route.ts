// src/app/api/cameras/[id]/latest-capture/download/route.ts
import { NextRequest, NextResponse } from "next/server"

const FASTAPI_BASE_URL =
  process.env.FASTAPI_URL ||
  process.env.NEXT_PUBLIC_FASTAPI_URL ||
  "http://localhost:8000"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const cameraId = parseInt(id)

  if (isNaN(cameraId)) {
    return NextResponse.json({ error: "Invalid camera ID" }, { status: 400 })
  }

  try {
    // Try the dedicated download endpoint first
    let response = await fetch(
      `${FASTAPI_BASE_URL}/api/cameras/${cameraId}/latest-capture/download`
    )
    let isUsingFallback = false

    // If that fails, fall back to the regular endpoint
    if (!response.ok) {
      console.warn(
        `Dedicated download endpoint failed for camera ${cameraId}, falling back to regular endpoint`
      )
      response = await fetch(
        `${FASTAPI_BASE_URL}/api/cameras/${cameraId}/latest-capture`
      )
      isUsingFallback = true
    }

    if (!response.ok) {
      return NextResponse.json(
        { error: "Failed to get latest capture" },
        { status: response.status }
      )
    }

    // Get the image data
    const imageBuffer = await response.arrayBuffer()
    const contentType = response.headers.get("content-type") || "image/jpeg"

    // Generate filename with timestamp
    let filename = `camera_${cameraId}_latest_capture.jpg`

    if (isUsingFallback) {
      // For fallback, generate timestamp ourselves
      const now = new Date()
      const timestamp = now
        .toISOString()
        .slice(0, 19)
        .replace(/[:-]/g, "")
        .replace("T", "_")
      filename = `camera_${cameraId}_${timestamp}.jpg`
    } else {
      // Try to get filename from response headers
      const contentDisposition = response.headers.get("content-disposition")
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(
          /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/
        )
        if (filenameMatch) {
          filename = filenameMatch[1].replace(/['"]/g, "")
        }
      }
    }

    return new NextResponse(imageBuffer, {
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=3600",
        "Content-Length": imageBuffer.byteLength.toString(),
        "Content-Disposition": `attachment; filename="${filename}"`,
      },
    })
  } catch (error) {
    console.error(
      `Failed to download latest capture for camera ${cameraId}:`,
      error
    )
    return NextResponse.json(
      { error: "Failed to download image" },
      { status: 500 }
    )
  }
}
