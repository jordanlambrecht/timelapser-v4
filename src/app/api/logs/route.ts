import { NextRequest, NextResponse } from 'next/server'
import { sql } from '@/lib/db'

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const limit = parseInt(searchParams.get('limit') || '50')
    const offset = parseInt(searchParams.get('offset') || '0')
    const cameraId = searchParams.get('camera_id')
    const level = searchParams.get('level')
    
    let logs
    let countResult
    
    // Handle different filter combinations
    if (cameraId && cameraId !== 'all' && level && level !== 'all') {
      const cameraIdInt = parseInt(cameraId)
      const levelUpper = level.toUpperCase()
      
      logs = await sql`
        SELECT l.*, c.name as camera_name 
        FROM logs l 
        LEFT JOIN cameras c ON l.camera_id = c.id 
        WHERE l.camera_id = ${cameraIdInt} AND l.level = ${levelUpper}
        ORDER BY l.timestamp DESC 
        LIMIT ${limit} OFFSET ${offset}
      `
      
      countResult = await sql`
        SELECT COUNT(*) as total 
        FROM logs l 
        WHERE l.camera_id = ${cameraIdInt} AND l.level = ${levelUpper}
      `
    } else if (cameraId && cameraId !== 'all') {
      const cameraIdInt = parseInt(cameraId)
      
      logs = await sql`
        SELECT l.*, c.name as camera_name 
        FROM logs l 
        LEFT JOIN cameras c ON l.camera_id = c.id 
        WHERE l.camera_id = ${cameraIdInt}
        ORDER BY l.timestamp DESC 
        LIMIT ${limit} OFFSET ${offset}
      `
      
      countResult = await sql`
        SELECT COUNT(*) as total 
        FROM logs l 
        WHERE l.camera_id = ${cameraIdInt}
      `
    } else if (level && level !== 'all') {
      const levelUpper = level.toUpperCase()
      
      logs = await sql`
        SELECT l.*, c.name as camera_name 
        FROM logs l 
        LEFT JOIN cameras c ON l.camera_id = c.id 
        WHERE l.level = ${levelUpper}
        ORDER BY l.timestamp DESC 
        LIMIT ${limit} OFFSET ${offset}
      `
      
      countResult = await sql`
        SELECT COUNT(*) as total 
        FROM logs l 
        WHERE l.level = ${levelUpper}
      `
    } else {
      logs = await sql`
        SELECT l.*, c.name as camera_name 
        FROM logs l 
        LEFT JOIN cameras c ON l.camera_id = c.id 
        ORDER BY l.timestamp DESC 
        LIMIT ${limit} OFFSET ${offset}
      `
      
      countResult = await sql`
        SELECT COUNT(*) as total FROM logs
      `
    }
    
    const total = parseInt(countResult[0].total)
    
    return NextResponse.json({
      logs,
      pagination: {
        total,
        limit,
        offset,
        hasMore: offset + limit < total
      }
    })
  } catch (error) {
    console.error('Database error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch logs' },
      { status: 500 }
    )
  }
}
