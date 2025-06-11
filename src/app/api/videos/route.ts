import { NextRequest, NextResponse } from 'next/server'
import { sql } from '@/lib/db'
import { exec } from 'child_process'
import { promisify } from 'util'
import path from 'path'

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
    const { 
      camera_id, 
      timelapse_id,
      video_name, 
      framerate = 30, 
      quality = 'medium',
      day_start = null,
      day_end = null 
    } = body
    
    // Validate required fields - need either camera_id or timelapse_id
    if (!camera_id && !timelapse_id) {
      return NextResponse.json(
        { error: 'Either camera_id or timelapse_id is required' },
        { status: 400 }
      )
    }

    // Trigger video generation using Python script with new timelapse support
    const pythonWorkerDir = '/Users/jordanlambrecht/dev-local/timelapser-v4/python-worker'
    const outputDir = '/Users/jordanlambrecht/dev-local/timelapser-v4/data/videos'
    
    // Build command - prefer timelapse_id if provided
    const activateCmd = `cd ${pythonWorkerDir} && source venv/bin/activate`
    let pythonCmd = ''
    
    if (timelapse_id) {
      // Use new timelapse-based generation
      pythonCmd = `python -c "
import sys
sys.path.append('.')
from video_generator import VideoGenerator
from database import Database

db = Database()
generator = VideoGenerator(db)

success, message, video_id = generator.generate_video_from_timelapse(
    timelapse_id=${timelapse_id},
    output_directory='${outputDir}',
    video_name=${video_name ? `'${video_name}'` : 'None'},
    framerate=${framerate},
    quality='${quality}',
    day_start=${day_start || 'None'},
    day_end=${day_end || 'None'}
)

print(f'SUCCESS:{success}')
print(f'MESSAGE:{message}')
print(f'VIDEO_ID:{video_id}')
"`
    } else {
      // Fallback to camera-based generation (legacy)
      const camera = await sql`SELECT * FROM cameras WHERE id = ${camera_id}`.then(r => r[0])
      if (!camera) {
        return NextResponse.json({ error: 'Camera not found' }, { status: 404 })
      }
      
      let imagesDir = `/Users/jordanlambrecht/dev-local/timelapser-v4/data/cameras/camera-${camera_id}/images`
      pythonCmd = `python video_generator.py "${imagesDir}" --with-db "${outputDir}"`
    }
    
    const fullCmd = `${activateCmd} && ${pythonCmd}`
    
    try {
      // Execute video generation (with timeout)
      const { stdout, stderr } = await execAsync(fullCmd, { 
        timeout: 300000, // 5 minute timeout
        env: { ...process.env, PATH: process.env.PATH }
      })
      
      console.log('Video generation output:', stdout)
      if (stderr) console.error('Video generation stderr:', stderr)
      
      if (timelapse_id) {
        // Parse new format output
        const successMatch = stdout.match(/SUCCESS:(true|false)/i)
        const messageMatch = stdout.match(/MESSAGE:(.+)/)
        const videoIdMatch = stdout.match(/VIDEO_ID:(\d+)/)
        
        const success = successMatch ? successMatch[1].toLowerCase() === 'true' : false
        const message = messageMatch ? messageMatch[1].trim() : 'Video generation completed'
        const videoId = videoIdMatch ? parseInt(videoIdMatch[1]) : null
        
        if (success && videoId) {
          // Fetch the created video record
          const videos = await sql`SELECT * FROM videos WHERE id = ${videoId}`
          
          return NextResponse.json({
            success: true,
            message: message,
            video: videos.length > 0 ? videos[0] : null,
            video_id: videoId
          })
        } else {
          return NextResponse.json({
            success: false,
            error: message || 'Video generation failed'
          }, { status: 400 })
        }
      } else {
        // Legacy format parsing
        const videoIdMatch = stdout.match(/Video ID: (\d+)/)
        const videoId = videoIdMatch ? parseInt(videoIdMatch[1]) : null
        
        if (videoId) {
          const videos = await sql`SELECT * FROM videos WHERE id = ${videoId}`
          
          return NextResponse.json({
            success: true,
            message: 'Video generation completed',
            video: videos.length > 0 ? videos[0] : null,
            video_id: videoId
          })
        }
        
        return NextResponse.json({
          success: true,
          message: 'Video generation initiated',
          output: stdout
        })
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
