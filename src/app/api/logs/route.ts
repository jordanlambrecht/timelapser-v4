import { NextRequest, NextResponse } from 'next/server';
import { sql } from '@/lib/db';

export async function GET(request: NextRequest) {
  try {
    // First, ensure logs table exists
    await sql`
      CREATE TABLE IF NOT EXISTS logs (
        id SERIAL PRIMARY KEY,
        level VARCHAR(10) NOT NULL,
        message TEXT NOT NULL,
        camera_id INTEGER REFERENCES cameras(id) ON DELETE SET NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `;

    const { searchParams } = new URL(request.url);
    const level = searchParams.get('level');
    const camera_id = searchParams.get('camera_id');
    const search = searchParams.get('search');
    const page = parseInt(searchParams.get('page') || '1');
    const limit = Math.min(parseInt(searchParams.get('limit') || '50'), 100);
    const offset = (page - 1) * limit;

    // Simple query to get all logs first
    let logsResult;
    let totalCount;
    
    if (!level || level === 'all') {
      // No filters - get all logs
      logsResult = await sql`
        SELECT 
          l.id,
          l.level,
          l.message,
          l.camera_id,
          l.timestamp,
          c.name as camera_name
        FROM logs l
        LEFT JOIN cameras c ON l.camera_id = c.id
        ORDER BY l.timestamp DESC
        LIMIT ${limit} OFFSET ${offset}
      `;
      
      totalCount = await sql`SELECT COUNT(*) as total FROM logs`;
    } else {
      // Filter by level
      logsResult = await sql`
        SELECT 
          l.id,
          l.level,
          l.message,
          l.camera_id,
          l.timestamp,
          c.name as camera_name
        FROM logs l
        LEFT JOIN cameras c ON l.camera_id = c.id
        WHERE l.level = ${level}
        ORDER BY l.timestamp DESC
        LIMIT ${limit} OFFSET ${offset}
      `;
      
      totalCount = await sql`SELECT COUNT(*) as total FROM logs WHERE level = ${level}`;
    }

    const total = parseInt(totalCount[0]?.total || '0');

    return NextResponse.json({
      logs: logsResult || [],
      pagination: {
        page,
        limit,
        total,
        pages: Math.ceil(total / limit)
      }
    });

  } catch (error) {
    console.error('Failed to fetch logs:', error);
    return NextResponse.json({ 
      error: 'Failed to fetch logs',
      details: error.message 
    }, { status: 500 });
  }
}