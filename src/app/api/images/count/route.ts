import { NextRequest, NextResponse } from 'next/server';
import { sql } from '@/lib/db';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const timelapseId = searchParams.get('timelapse_id');
    const cameraId = searchParams.get('camera_id');

    if (!timelapseId && !cameraId) {
      return NextResponse.json({ error: 'timelapse_id or camera_id required' }, { status: 400 });
    }

    let count = 0;

    try {
      let result;
      if (timelapseId) {
        result = await sql`
          SELECT COUNT(*) as count 
          FROM images 
          WHERE timelapse_id = ${parseInt(timelapseId)}
        `;
      } else if (cameraId) {
        result = await sql`
          SELECT COUNT(*) as count 
          FROM images 
          WHERE camera_id = ${parseInt(cameraId)}
        `;
      }

      if (result && result.length > 0) {
        count = parseInt(result[0].count);
      }
    } catch (error) {
      // Images table might not exist yet
      console.log('Images table query failed:', error);
      count = 0;
    }

    return NextResponse.json({ count });
  } catch (error) {
    console.error('Failed to get image count:', error);
    return NextResponse.json({ count: 0 });
  }
}