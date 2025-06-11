import { NextRequest, NextResponse } from 'next/server'
import { sql } from '@/lib/db'
import fs from 'fs/promises'
import path from 'path'

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const videoId = parseInt(params.id)
    
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

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const videoId = parseInt(params.id)
    
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
