// src/app/api/videos/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI, proxyToFastAPIWithQuery } from "@/lib/fastapi-proxy"

// Import eventEmitter for broadcasting changes
import { eventEmitter } from "@/app/api/events/route"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)

  // Proxy to FastAPI backend with query parameters
  return proxyToFastAPIWithQuery("/api/videos", searchParams)
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { camera_id, video_name } = body

    if (!camera_id) {
      return NextResponse.json(
        { error: "camera_id is required" },
        { status: 400 }
      )
    }

    // Validate camera_id is a positive integer
    const cameraId = parseInt(camera_id)
    if (isNaN(cameraId) || cameraId <= 0) {
      return NextResponse.json(
        { error: "camera_id must be a positive integer" },
        { status: 400 }
      )
    }

    // Validate video_name if provided
    if (video_name) {
      const videoNameStr = String(video_name).trim()
      if (videoNameStr.length === 0 || videoNameStr.length > 100) {
        return NextResponse.json(
          { error: "video_name must be between 1 and 100 characters" },
          { status: 400 }
        )
      }

      // Check for invalid characters
      if (!/^[a-zA-Z0-9\s\-_.]+$/.test(videoNameStr)) {
        return NextResponse.json(
          {
            error:
              "video_name contains invalid characters. Only letters, numbers, spaces, hyphens, underscores, and dots are allowed.",
          },
          { status: 400 }
        )
      }

      // Prevent path traversal
      if (
        videoNameStr.includes("..") ||
        videoNameStr.includes("/") ||
        videoNameStr.includes("\\")
      ) {
        return NextResponse.json(
          { error: "video_name cannot contain path separators or .." },
          { status: 400 }
        )
      }
    }

    // Use secure FastAPI endpoint for video generation
    const response = await proxyToFastAPI("/api/videos/generate", {
      method: "POST",
      body: {
        camera_id: cameraId,
        video_name: video_name || null,
      },
    })

    if (response.status === 200) {
      const result = await response.json()

      // Broadcast video generation started event
      eventEmitter.emit({
        type: "video_generation_started",
        camera_id: cameraId,
        video_id: result.video_id,
        video_name: result.video_name,
        timestamp: new Date().toISOString(),
      })

      return NextResponse.json({
        success: true,
        message: result.message,
        video_id: result.video_id,
        video_name: result.video_name,
      })
    } else {
      const error = await response
        .json()
        .catch(() => ({ error: "Unknown error" }))

      // Broadcast video failed event
      eventEmitter.emit({
        type: "video_failed",
        camera_id: cameraId,
        error: error.detail || error.error || "Video generation failed",
        timestamp: new Date().toISOString(),
      })

      return NextResponse.json(
        {
          success: false,
          error: error.detail || error.error || "Video generation failed",
        },
        { status: response.status }
      )
    }
  } catch (error) {
    console.error("Video generation error:", error)
    return NextResponse.json(
      { error: "Failed to generate video" },
      { status: 500 }
    )
  }
}
