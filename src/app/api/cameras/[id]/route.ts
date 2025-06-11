import { NextRequest, NextResponse } from 'next/server'
import { sql } from '@/lib/db'

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const cameraId = parseInt(params.id)
    
    if (isNaN(cameraId)) {
      return NextResponse.json(
        { error: 'Invalid camera ID' },
        { status: 400 }
      )
    }

    // Delete camera (timelapses will be deleted via CASCADE)
    const result = await sql`
      DELETE FROM cameras 
      WHERE id = ${cameraId}
      RETURNING *
    `
    
    if (result.length === 0) {
      return NextResponse.json(
        { error: 'Camera not found' },
        { status: 404 }
      )
    }
    
    return NextResponse.json({ message: 'Camera deleted successfully' })
  } catch (error) {
    console.error('Database error:', error)
    return NextResponse.json(
      { error: 'Failed to delete camera' },
      { status: 500 }
    )
  }
}
