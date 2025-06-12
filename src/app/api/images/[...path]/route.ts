import { NextRequest, NextResponse } from 'next/server'
import { readFile } from 'fs/promises'
import { join } from 'path'
import { existsSync } from 'fs'

export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  try {
    // Join the path segments to create the full path
    const imagePath = params.path.join('/')
    
    // Build the full file path - images are stored in /data/cameras/
    const fullPath = join(process.cwd(), 'data', imagePath)
    
    // Security check: ensure the path doesn't escape the data directory
    const dataDir = join(process.cwd(), 'data')
    if (!fullPath.startsWith(dataDir)) {
      return NextResponse.json({ error: 'Invalid path' }, { status: 400 })
    }
    
    // Check if file exists
    if (!existsSync(fullPath)) {
      return NextResponse.json({ error: 'Image not found' }, { status: 404 })
    }
    
    // Read the image file
    const imageBuffer = await readFile(fullPath)
    
    // Determine content type based on file extension
    const extension = fullPath.split('.').pop()?.toLowerCase()
    let contentType = 'image/jpeg' // default
    
    switch (extension) {
      case 'png':
        contentType = 'image/png'
        break
      case 'gif':
        contentType = 'image/gif'
        break
      case 'webp':
        contentType = 'image/webp'
        break
      case 'jpg':
      case 'jpeg':
      default:
        contentType = 'image/jpeg'
        break
    }
    
    // Return the image with appropriate headers
    return new NextResponse(imageBuffer, {
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=3600', // Cache for 1 hour
      },
    })
    
  } catch (error) {
    console.error('Error serving image:', error)
    return NextResponse.json(
      { error: 'Failed to serve image' },
      { status: 500 }
    )
  }
}
