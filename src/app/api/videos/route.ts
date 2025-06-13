import { NextRequest, NextResponse } from 'next/server'
import { sql } from '@/lib/db'
import { exec } from 'child_process'
import { promisify } from 'util'
import path from 'path'

// Import eventEmitter for broadcasting changes
import { eventEmitter } from '@/app/api/events/route'

const execAsync = promisify(exec)

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const cameraId = searchParams.get('camera_id')
    const status = searchParams.get('status')
    
    let videos
    
    // Handle different filter combinations
    if (cameraId && cameraId !== 'all' && status && status !== 'all') {
      videos = await sql`
        SELECT v.*, c.name as camera_name 
        FROM videos v 
        LEFT JOIN cameras c ON v.camera_id = c.id 
        WHERE v.camera_id = ${parseInt(cameraId)} AND v.status = ${status}
        ORDER BY v.created_at DESC
      `
    } else if (cameraId && cameraId !== 'all') {
      videos = await sql`
        SELECT v.*, c.name as camera_name 
        FROM videos v 
        LEFT JOIN cameras c ON v.camera_id = c.id 
        WHERE v.camera_id = ${parseInt(cameraId)}
        ORDER BY v.created_at DESC
      `
    } else if (status && status !== 'all') {
      videos = await sql`
        SELECT v.*, c.name as camera_name 
        FROM videos v 
        LEFT JOIN cameras c ON v.camera_id = c.id 
        WHERE v.status = ${status}
        ORDER BY v.created_at DESC
      `
    } else {
      videos = await sql`
        SELECT v.*, c.name as camera_name 
        FROM videos v 
        LEFT JOIN cameras c ON v.camera_id = c.id 
        ORDER BY v.created_at DESC
      `
    }
    
    return NextResponse.json(videos)
  } catch (error) {
    console.error('Database error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch videos' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { camera_id, video_name } = body
    
    if (!camera_id) {
      return NextResponse.json(
        { error: 'camera_id is required' },
        { status: 400 }
      )
    }

    // Get camera details
    const cameras = await sql`SELECT * FROM cameras WHERE id = ${camera_id}`
    if (cameras.length === 0) {
      return NextResponse.json({ error: 'Camera not found' }, { status: 404 })
    }
    
    const camera = cameras[0]

    // Get active timelapse for this camera
    const timelapses = await sql`
      SELECT * FROM timelapses 
      WHERE camera_id = ${camera_id} AND status = 'running'
      ORDER BY created_at DESC 
      LIMIT 1
    `
    
    if (timelapses.length === 0) {
      return NextResponse.json({
        error: 'No active timelapse found for this camera. Start a timelapse first.'
      }, { status: 400 })
    }
    
    const timelapse = timelapses[0]

    // Check if there are images for this timelapse
    const images = await sql`
      SELECT COUNT(*) as count FROM images WHERE timelapse_id = ${timelapse.id}
    `
    
    const imageCount = images[0]?.count || 0
    if (imageCount === 0) {
      return NextResponse.json({
        error: 'No images found for this timelapse. Capture some images first.'
      }, { status: 400 })
    }

    // Trigger video generation using Python worker
    const pythonWorkerDir = '/Users/jordanlambrecht/dev-local/timelapser-v4/backend'
    
    const pythonCmd = `cd ${pythonWorkerDir} && source venv/bin/activate && python -c "
import sys
sys.path.append('.')
from video_generator import VideoGenerator
from app.database import SyncDatabase
import os

# Create database and video generator instances
db = SyncDatabase()
db.initialize()  # Initialize the database pool

generator = VideoGenerator(db)

# Generate video for timelapse
timelapse_id = ${timelapse.id}
camera_name = '${camera.name.replace(/'/g, "\\'")}'
output_directory = '/Users/jordanlambrecht/dev-local/timelapser-v4/data/videos'

# Create output directory if it doesn't exist
os.makedirs(output_directory, exist_ok=True)

try:
    success, message, video_id = generator.generate_video_from_timelapse_with_overlays(
        timelapse_id=timelapse_id,
        output_directory=output_directory,
        video_name='${video_name ? video_name.replace(/'/g, "\\'") : ''}' or None,
        framerate=30,
        quality='medium'
    )
    
    print(f'SUCCESS:{success}')
    print(f'MESSAGE:{message}')
    print(f'VIDEO_ID:{video_id}')
finally:
    # Clean up database connection
    db.close()
"`
    
    try {
      // Execute video generation (with timeout)
      const { stdout, stderr } = await execAsync(pythonCmd, { 
        timeout: 300000, // 5 minute timeout
        env: { ...process.env, PATH: process.env.PATH }
      })
      
      console.log('Video generation output:', stdout)
      if (stderr) console.error('Video generation stderr:', stderr)
      
      // Parse output
      const successMatch = stdout.match(/SUCCESS:(true|false)/i)
      const messageMatch = stdout.match(/MESSAGE:(.+)/)
      const videoIdMatch = stdout.match(/VIDEO_ID:(\d+|None)/)
      
      const success = successMatch ? successMatch[1].toLowerCase() === 'true' : false
      const message = messageMatch ? messageMatch[1].trim() : 'Video generation completed'
      const videoId = videoIdMatch && videoIdMatch[1] !== 'None' ? parseInt(videoIdMatch[1]) : null
      
      if (success && videoId) {
        // Fetch the created video record
        const videos = await sql`SELECT * FROM videos WHERE id = ${videoId}`
        const video = videos.length > 0 ? videos[0] : null
        
        // Broadcast video completed event
        eventEmitter.emit({
          type: 'video_completed',
          camera_id: camera_id,
          video: video,
          timestamp: new Date().toISOString()
        })
        
        return NextResponse.json({
          success: true,
          message: message,
          video: video,
          video_id: videoId
        })
      } else {
        // Broadcast video failed event
        eventEmitter.emit({
          type: 'video_failed',
          camera_id: camera_id,
          error: message || 'Video generation failed',
          timestamp: new Date().toISOString()
        })
        
        return NextResponse.json({
          success: false,
          error: message || 'Video generation failed'
        }, { status: 400 })
      }
      
    } catch (execError: any) {
      console.error('Video generation failed:', execError)
      
      return NextResponse.json({
        success: false,
        error: 'Video generation failed',
        details: execError.message
      }, { status: 500 })
    }
    
  } catch (error) {
    console.error('API error:', error)
    return NextResponse.json(
      { error: 'Failed to process video generation request' },
      { status: 500 }
    )
  }
}
