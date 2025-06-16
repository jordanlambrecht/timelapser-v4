import { NextRequest, NextResponse } from "next/server"
import { readFile } from "fs/promises"
import { join } from "path"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  try {
    // Await params first
    const { path } = await params

    // Reconstruct the full file path
    const filePath = path.join("/")

    // Security: Ensure we're only serving files from the data directory
    const dataDir =
      process.env.DATA_DIR ||
      "/Users/jordanlambrecht/dev-local/timelapser-v4/data"
    const fullPath = join(dataDir, filePath)

    // Additional security: Ensure the resolved path is within the data directory
    if (!fullPath.startsWith(dataDir)) {
      return NextResponse.json({ error: "Invalid file path" }, { status: 403 })
    }

    // Read the file
    const fileBuffer = await readFile(fullPath)

    // Determine content type based on file extension
    const extension = filePath.split(".").pop()?.toLowerCase()
    let contentType = "application/octet-stream"

    switch (extension) {
      case "jpg":
      case "jpeg":
        contentType = "image/jpeg"
        break
      case "png":
        contentType = "image/png"
        break
      case "gif":
        contentType = "image/gif"
        break
      case "webp":
        contentType = "image/webp"
        break
    }

    // Return the file with appropriate headers
    return new NextResponse(fileBuffer, {
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=3600", // Cache for 1 hour
        "Content-Length": fileBuffer.length.toString(),
      },
    })
  } catch (error) {
    console.error("Failed to serve image:", error)

    // Return a 404 if file not found, or 500 for other errors
    if (error instanceof Error && "code" in error && error.code === "ENOENT") {
      return NextResponse.json({ error: "Image not found" }, { status: 404 })
    }

    return NextResponse.json(
      { error: "Failed to serve image" },
      { status: 500 }
    )
  }
}
