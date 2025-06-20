// src/app/api/images/[id]/download/route.ts
import { NextRequest, NextResponse } from "next/server"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params

  try {
    // Proxy to FastAPI backend
    const fastApiUrl = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000"
    const response = await fetch(`${fastApiUrl}/api/images/${id}/download`)

    if (!response.ok) {
      return NextResponse.json(
        { error: "Image not found" },
        { status: response.status }
      )
    }

    // Stream the image data
    const imageBuffer = await response.arrayBuffer()
    const contentType = response.headers.get("content-type") || "image/jpeg"
    const contentDisposition = response.headers.get("content-disposition")

    return new NextResponse(imageBuffer, {
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=3600",
        "Content-Length": imageBuffer.byteLength.toString(),
        ...(contentDisposition && { "Content-Disposition": contentDisposition }),
      },
    })
  } catch (error) {
    console.error("Failed to download image:", error)
    return NextResponse.json(
      { error: "Failed to download image" },
      { status: 500 }
    )
  }
}
