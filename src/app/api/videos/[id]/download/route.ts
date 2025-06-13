import { NextRequest, NextResponse } from "next/server"
import { sql } from "@/lib/db"
import fs from "fs"
import path from "path"

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

    // Get video details
    const videos = await sql`
      SELECT * FROM videos WHERE id = ${videoId}
    `

    if (videos.length === 0) {
      return NextResponse.json({ error: "Video not found" }, { status: 404 })
    }

    const video = videos[0]

    if (!video.file_path || video.status !== "completed") {
      return NextResponse.json(
        { error: "Video file not available" },
        { status: 404 }
      )
    }

    // Check if file exists
    if (!fs.existsSync(video.file_path)) {
      return NextResponse.json(
        { error: "Video file not found on disk" },
        { status: 404 }
      )
    }

    // Read the file
    const fileBuffer = fs.readFileSync(video.file_path)
    const fileName = path.basename(video.file_path)

    // Create response with proper headers for video download
    const response = new NextResponse(fileBuffer)

    response.headers.set("Content-Type", "video/mp4")
    response.headers.set(
      "Content-Disposition",
      `attachment; filename="${fileName}"`
    )
    response.headers.set("Content-Length", fileBuffer.length.toString())

    return response
  } catch (error) {
    console.error("Download error:", error)
    return NextResponse.json(
      { error: "Failed to download video" },
      { status: 500 }
    )
  }
}
