import { NextRequest, NextResponse } from 'next/server'
import { readFile } from 'fs/promises'
import { join } from 'path'
import { sql } from '@/lib/db'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const cameraId = parseInt(id)

    if (isNaN(cameraId)) {
      return NextResponse.json({ error: 'Invalid camera ID' }, { status: 400 })
    }

    // Get the latest image for this camera
    const result = await sql`
      SELECT file_path, captured_at 
      FROM images 
      WHERE camera_id = ${cameraId}
      ORDER BY captured_at DESC 
      LIMIT 1
    `
    
    if (result.length === 0) {
      // No images captured yet - return a placeholder
      return NextResponse.json({ error: 'No images captured yet' }, { status: 404 })
    }

    const latestImage = result[0]
    
    // Handle both absolute and relative paths
    let imagePath: string
    if (latestImage.file_path.startsWith('/')) {
      // Already absolute path
      imagePath = latestImage.file_path
    } else {
      // Relative path, join with project root
      imagePath = join(process.cwd(), latestImage.file_path)
    }

    try {
      // Read the image file
      const imageBuffer = await readFile(imagePath)
      
      // Return the image with proper headers
      return new NextResponse(imageBuffer, {
        status: 200,
        headers: {
          'Content-Type': 'image/jpeg',
          'Cache-Control': 'public, max-age=60', // Cache for 1 minute
          'Last-Modified': new Date(latestImage.captured_at).toUTCString(),
        },
      })
    } catch (fileError) {
      console.error('Error reading image file:', fileError)
      return NextResponse.json({ error: 'Image file not found' }, { status: 404 })
    }

  } catch (error) {
    console.error('Error fetching latest capture:', error)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}