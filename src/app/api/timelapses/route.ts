import { NextRequest, NextResponse } from 'next/server'
import { sql } from '@/lib/db'

export async function GET() {
  try {
    const timelapses = await sql`
      SELECT * FROM timelapses 
      ORDER BY created_at DESC
    `
    
    return NextResponse.json(timelapses)
  } catch (error) {
    console.error('Database error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch timelapses' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const { camera_id, status } = await request.json()
    
    if (!camera_id || !status) {
      return NextResponse.json(
        { error: 'Camera ID and status are required' },
        { status: 400 }
      )
    }

    // If starting a timelapse, validate camera readiness
    if (status === 'running') {
      // Check if camera exists and is enabled (active)
      const camera = await sql`
        SELECT * FROM cameras 
        WHERE id = ${camera_id} AND status = 'active'
      `

      if (camera.length === 0) {
        return NextResponse.json(
          { 
            error: 'Camera not found or disabled',
            details: 'Camera must be enabled (active status) to start timelapse'
          },
          { status: 400 }
        )
      }

      const cameraData = camera[0]

      // Check if camera is online/connectable
      if (cameraData.health_status === 'offline') {
        return NextResponse.json(
          { 
            error: 'Camera is offline',
            details: 'Camera must be online and connectable to start timelapse. Check RTSP connection.'
          },
          { status: 400 }
        )
      }

      // Additional check: Test RTSP connection if health status is unknown
      if (cameraData.health_status === 'unknown' || !cameraData.last_capture_at) {
        try {
          // Call Python worker to test connection
          const { exec } = await import('child_process')
          const { promisify } = await import('util')
          const execAsync = promisify(exec)
          
          const pythonWorkerDir = '/Users/jordanlambrecht/dev-local/timelapser-v4/python-worker'
          const testCmd = `cd ${pythonWorkerDir} && source venv/bin/activate && python -c "
import sys
sys.path.append('.')
from capture import RTSPCapture
capture = RTSPCapture()
success, message = capture.test_rtsp_connection('${cameraData.rtsp_url}')
print(f'SUCCESS:{success}')
print(f'MESSAGE:{message}')
"`

          const { stdout } = await execAsync(testCmd, { timeout: 15000 })
          
          const successMatch = stdout.match(/SUCCESS:(true|false)/i)
          const success = successMatch ? successMatch[1].toLowerCase() === 'true' : false
          
          if (!success) {
            // Update camera health status to offline
            await sql`
              UPDATE cameras 
              SET health_status = 'offline', updated_at = CURRENT_TIMESTAMP
              WHERE id = ${camera_id}
            `
            
            return NextResponse.json(
              { 
                error: 'Camera connection test failed',
                details: 'Unable to connect to camera RTSP stream. Please check camera settings and network connectivity.'
              },
              { status: 400 }
            )
          }

          // Update camera health status to online since test passed
          await sql`
            UPDATE cameras 
            SET health_status = 'online', updated_at = CURRENT_TIMESTAMP
            WHERE id = ${camera_id}
          `
          
        } catch (testError) {
          console.error('Camera connection test failed:', testError)
          return NextResponse.json(
            { 
              error: 'Camera connection test timeout',
              details: 'Camera connection test timed out. Camera may be unreachable.'
            },
            { status: 400 }
          )
        }
      }
    }

    // Validation passed, proceed with timelapse update
    // Check if timelapse already exists for this camera
    const existing = await sql`
      SELECT * FROM timelapses 
      WHERE camera_id = ${camera_id}
    `

    let result
    if (existing.length > 0) {
      // Update existing timelapse
      if (status === 'running') {
        // Set start_date when starting
        result = await sql`
          UPDATE timelapses 
          SET status = ${status}, start_date = CURRENT_DATE, updated_at = CURRENT_TIMESTAMP
          WHERE camera_id = ${camera_id}
          RETURNING *
        `
      } else {
        // Just update status when stopping
        result = await sql`
          UPDATE timelapses 
          SET status = ${status}, updated_at = CURRENT_TIMESTAMP
          WHERE camera_id = ${camera_id}
          RETURNING *
        `
      }
    } else {
      // Create new timelapse
      result = await sql`
        INSERT INTO timelapses (camera_id, status, start_date)
        VALUES (${camera_id}, ${status}, ${status === 'running' ? 'CURRENT_DATE' : 'NULL'})
        RETURNING *
      `
    }
    
    return NextResponse.json({ 
      success: true, 
      timelapse: result[0],
      message: status === 'running' ? 'Timelapse started successfully' : 'Timelapse stopped'
    })
  } catch (error) {
    console.error('Database error:', error)
    return NextResponse.json(
      { error: 'Failed to update timelapse' },
      { status: 500 }
    )
  }
}
