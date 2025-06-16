// src/app/api/videos/[id]/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"
import fs from "fs/promises"
import path from "path"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params

  // Proxy to FastAPI backend
  return proxyToFastAPI(`/api/videos/${id}`)
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const body = await request.json()

    // Proxy to FastAPI backend
    return proxyToFastAPI(`/api/videos/${id}`, {
      method: "PUT",
      body,
    })
  } catch (error) {
    console.error("Failed to update video:", error)
    return NextResponse.json(
      { error: "Failed to update video" },
      { status: 500 }
    )
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params

    // Get video info before deletion for file cleanup
    const videoResponse = await proxyToFastAPI(`/api/videos/${id}`)

    if (videoResponse.status === 200) {
      const video = await videoResponse.json()

      // Delete the video file if it exists
      if (video.file_path) {
        try {
          const fullPath = path.isAbsolute(video.file_path)
            ? video.file_path
            : path.join(process.cwd(), video.file_path)

          await fs.unlink(fullPath)
          console.log(`Deleted video file: ${fullPath}`)
        } catch (fileError) {
          console.warn(
            `Failed to delete video file: ${video.file_path}`,
            fileError
          )
          // Continue with database deletion even if file deletion fails
        }
      }
    }

    // Proxy delete to FastAPI backend
    return proxyToFastAPI(`/api/videos/${id}`, {
      method: "DELETE",
    })
  } catch (error) {
    console.error("Failed to delete video:", error)
    return NextResponse.json(
      { error: "Failed to delete video" },
      { status: 500 }
    )
  }
}
