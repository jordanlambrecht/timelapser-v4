import { NextResponse } from 'next/server';
import { sql } from '@/lib/db';

export async function GET() {
  try {
    // Ensure logs table exists
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

    // Get log counts by level
    const result = await sql`
      SELECT 
        level,
        COUNT(*) as count
      FROM logs 
      GROUP BY level
    `;
    
    // Initialize stats with zeros
    const stats = {
      errors: 0,
      warnings: 0,
      info: 0,
      debug: 0,
      total: 0
    };
    
    // Process the results
    let total = 0;
    result.forEach((row: any) => {
      const count = parseInt(row.count);
      total += count;
      
      switch (row.level.toLowerCase()) {
        case 'error':
          stats.errors = count;
          break;
        case 'warning':
        case 'warn':
          stats.warnings = count;
          break;
        case 'info':
          stats.info = count;
          break;
        case 'debug':
          stats.debug = count;
          break;
      }
    });
    
    stats.total = total;
    
    return NextResponse.json(stats);
    
  } catch (error) {
    console.error('Failed to fetch log stats:', error);
    return NextResponse.json({ 
      errors: 0, 
      warnings: 0, 
      info: 0, 
      debug: 0, 
      total: 0,
      error: error.message 
    });
  }
}