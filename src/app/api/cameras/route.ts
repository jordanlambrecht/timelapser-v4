import { NextRequest, NextResponse } from 'next/server'
import { sql } from '@/lib/db'

export async function GET() {
  try {
    const cameras = await sql`
      SELECT * FROM cameras 
      ORDER BY created_at DESC
    `
    
    return NextResponse.json(cameras)
  } catch (error) {
    console.error('Database error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch cameras' },
      { status: 500 }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const { name, rtsp_url, use_time_window, time_window_start, time_window_end } = await request.json()
    
    if (!name || !rtsp_url) {
      return NextResponse.json(
        { error: 'Name and RTSP URL are required' },
        { status: 400 }
      )
    }

    // Use default values for optional fields
    const timeWindowEnabled = use_time_window || false
    const startTime = time_window_start ? time_window_start + ':00' : '06:00:00'
    const endTime = time_window_end ? time_window_end + ':00' : '18:00:00'

    const result = await sql`
      INSERT INTO cameras (
        name, 
        rtsp_url, 
        status,
        use_time_window,
        time_window_start,
        time_window_end
      ) VALUES (
        ${name}, 
        ${rtsp_url}, 
        'active',
        ${timeWindowEnabled},
        ${startTime},
        ${endTime}
      ) RETURNING *
    `
    
    return NextResponse.json(result[0], { status: 201 })
  } catch (error) {
    console.error('Database error:', error)
    return NextResponse.json(
      { error: 'Failed to create camera' },
      { status: 500 }
    )
  }
}
