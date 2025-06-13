import { NextRequest, NextResponse } from 'next/server'
import { sql } from '@/lib/db'
import fs from 'fs/promises'
import path from 'path'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const videoId = parseInt(id)
    
    if (isNaN(videoId)) {
      return NextResponse.json(
        { error: 'Invalid video ID' },
        { status: 400 }
      )
    }

    const videos = await sql`
      SELECT v.*, c.name as camera_name 
      FROM videos v 
      LEFT JOIN cameras c ON v.camera_id = c.id 
      WHERE v.id = ${videoId}
    `
    
    if (videos.length === 0) {
      return NextResponse.json(
        { error: 'Video not found' },
        { status: 404 }
      )
    }
    
    return NextResponse.json(videos[0])
  } catch (error) {
    console.error('Database error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch video' },
      { status: 500 }
    )
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const videoId = parseInt(id)
    
    if (isNaN(videoId)) {
      return NextResponse.json(
        { error: 'Invalid video ID' },
        { status: 400 }
      )
    }

    const body = await request.json()
    const { name } = body

    if (!name || name.trim() === '') {
      return NextResponse.json(
        { error: 'Name is required' },
        { status: 400 }
      )
    }

    // Get current video details
    const videos = await sql`
      SELECT * FROM videos WHERE id = ${videoId}
    `
    
    if (videos.length === 0) {
      return NextResponse.json(
        { error: 'Video not found' },
        { status: 404 }
      )
    }

    const currentVideo = videos[0]
    
    // Rename the actual file if it exists
    if (currentVideo.file_path) {
      try {
        const dir = path.dirname(currentVideo.file_path)
        const newFileName = `${name.trim()}.mp4`
        const newFilePath = path.join(dir, newFileName)
        
        // Rename the file
        await fs.rename(currentVideo.file_path, newFilePath)
        
        // Update database with new file path
        await sql`
          UPDATE videos 
          SET file_path = ${newFilePath}, updated_at = CURRENT_TIMESTAMP
          WHERE id = ${videoId}
        `
        
        console.log(`Renamed video file from ${currentVideo.file_path} to ${newFilePath}`)
      } catch (fileError) {
        console.error(`Failed to rename video file: ${currentVideo.file_path}`, fileError)
        return NextResponse.json(
          { error: 'Failed to rename video file' },
          { status: 500 }
        )
      }
    }
    
    // Get updated video details
    const updatedVideos = await sql`
      SELECT v.*, c.name as camera_name 
      FROM videos v 
      LEFT JOIN cameras c ON v.camera_id = c.id 
      WHERE v.id = ${videoId}
    `
    
    return NextResponse.json({
      message: 'Video renamed successfully',
      video: updatedVideos[0]
    })
  } catch (error) {
    console.error('Rename error:', error)
    return NextResponse.json(
      { error: 'Failed to rename video' },
      { status: 500 }
    )
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const videoId = parseInt(id)
    
    if (isNaN(videoId)) {
      return NextResponse.json(
        { error: 'Invalid video ID' },
        { status: 400 }
      )
    }

    // Get video details first
    const videos = await sql`
      SELECT * FROM videos WHERE id = ${videoId}
    `
    
    if (videos.length === 0) {
      return NextResponse.json(
        { error: 'Video not found' },
        { status: 404 }
      )
    }
    
    const video = videos[0]
    
    // Delete the video file if it exists
    if (video.file_path) {
      try {
        await fs.unlink(video.file_path)
        console.log(`Deleted video file: ${video.file_path}`)
      } catch (fileError) {
        console.warn(`Failed to delete video file: ${video.file_path}`, fileError)
        // Continue with database deletion even if file deletion fails
      }
    }
    
    // Delete from database
    await sql`
      DELETE FROM videos WHERE id = ${videoId}
    `
    
    return NextResponse.json({ 
      message: 'Video deleted successfully',
      deleted_video: video.name
    })
  } catch (error) {
    console.error('Delete error:', error)
    return NextResponse.json(
      { error: 'Failed to delete video' },
      { status: 500 }
    )
  }
}
