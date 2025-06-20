// src/app/api/images/[id]/thumbnail/route.ts
import { NextRequest, NextResponse } from "next/server"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params

  try {
    // Proxy to FastAPI backend
    const fastApiUrl = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000"
    const response = await fetch(`${fastApiUrl}/api/images/${id}/thumbnail`)

    if (!response.ok) {
      return NextResponse.json(
        { error: "Image not found" },
        { status: response.status }
      )
    }

    // Stream the image data
    const imageBuffer = await response.arrayBuffer()
    const contentType = response.headers.get("content-type") || "image/jpeg"

    return new NextResponse(imageBuffer, {
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=3600",
        "Content-Length": imageBuffer.byteLength.toString(),
      },
    })
  } catch (error) {
    console.error("Failed to get image thumbnail:", error)
    return NextResponse.json(
      { error: "Failed to get image thumbnail" },
      { status: 500 }
    )
  }
}
