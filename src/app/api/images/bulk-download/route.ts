import { NextRequest, NextResponse } from "next/server"

const FASTAPI_BASE_URL =
  process.env.FASTAPI_URL ||
  process.env.NEXT_PUBLIC_FASTAPI_URL ||
  "http://localhost:8000"

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    // Try the dedicated bulk download endpoint first
    let response = await fetch(`${FASTAPI_BASE_URL}/api/images/bulk-download`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    })
    let isUsingFallback = false

    // If that fails, fall back to individual image downloads
    if (!response.ok) {
      console.warn(
        "Bulk download endpoint failed, falling back to individual downloads"
      )
      isUsingFallback = true

      // TODO: Implement fallback logic for individual image downloads
      // For now, we'll still try to handle the original response
    }

    if (!response.ok && !isUsingFallback) {
      const errorText = await response.text()
      return NextResponse.json(
        { error: "Failed to download images", details: errorText },
        { status: response.status }
      )
    }

    if (isUsingFallback) {
      // Handle fallback logic here
      return NextResponse.json(
        {
          error: "Bulk download not available, please try individual downloads",
        },
        { status: 503 }
      )
    }

    // Get the ZIP file data
    const arrayBuffer = await response.arrayBuffer()

    // Generate filename with timestamp
    const now = new Date()
    const timestamp = now
      .toISOString()
      .slice(0, 19)
      .replace(/[:-]/g, "")
      .replace("T", "_")

    let filename = `images_bulk_download_${timestamp}.zip`

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

    // Return the ZIP file with proper headers
    return new NextResponse(arrayBuffer, {
      status: 200,
      headers: {
        "Content-Type": "application/zip",
        "Content-Disposition": `attachment; filename="${filename}"`,
      },
    })
  } catch (error) {
    console.error("Bulk download error:", error)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}
