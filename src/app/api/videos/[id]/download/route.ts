// src/app/api/videos/[id]/download/route.ts
import { NextRequest, NextResponse } from "next/server"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const videoId = parseInt(id)

    if (isNaN(videoId)) {
      return NextResponse.json({ error: "Invalid video ID" }, { status: 400 })
    }

    // Proxy to FastAPI backend for secure video download
    const fastApiUrl =
      process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000"
    const response = await fetch(
      `${fastApiUrl}/api/videos/${videoId}/download`,
      {
        method: "GET",
      }
    )

    if (!response.ok) {
      const errorData = await response
        .json()
        .catch(() => ({ error: "Unknown error" }))
      return NextResponse.json(errorData, { status: response.status })
    }

    // Stream the video file from FastAPI
    const contentType = response.headers.get("content-type") || "video/mp4"
    const contentDisposition =
      response.headers.get("content-disposition") ||
      `attachment; filename="video_${id}.mp4"`

    return new NextResponse(response.body, {
      status: 200,
      headers: {
        "Content-Type": contentType,
        "Content-Disposition": contentDisposition,
      },
    })
  } catch (error) {
    console.error("Failed to download video:", error)
    return NextResponse.json(
      { error: "Failed to download video" },
      { status: 500 }
    )
  }
}
