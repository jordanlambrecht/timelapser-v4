import { NextRequest, NextResponse } from 'next/server';
import { sql } from '@/lib/db';

// Import eventEmitter for broadcasting changes
import { eventEmitter } from '@/app/api/events/route';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const cameraId = parseInt(id);

    // Get camera details
    const cameraResult = await sql`
      SELECT * FROM cameras WHERE id = ${cameraId}
    `;
    
    if (cameraResult.length === 0) {
      return NextResponse.json({ error: 'Camera not found' }, { status: 404 });
    }

    const camera = cameraResult[0];

    // Get active timelapse
    const timelapseResult = await sql`
      SELECT * FROM timelapses 
      WHERE camera_id = ${cameraId} AND status = 'running'
      ORDER BY created_at DESC 
      LIMIT 1
    `;
    const activeTimelapse = timelapseResult[0] || null;

    // Get latest image
    const latestImageResult = await sql`
      SELECT * FROM images 
      WHERE camera_id = ${cameraId}
      ORDER BY captured_at DESC 
      LIMIT 1
    `;
    const latestImage = latestImageResult[0] || null;

    // Get image count for active timelapse
    let imageCount = 0;
    if (activeTimelapse) {
      const imageCountResult = await sql`
        SELECT COUNT(*) as count FROM images 
        WHERE timelapse_id = ${activeTimelapse.id}
      `;
      imageCount = parseInt(imageCountResult[0].count);
    }

    // Get total images for camera
    const totalImagesResult = await sql`
      SELECT COUNT(*) as count FROM images 
      WHERE camera_id = ${cameraId}
    `;
    const totalImages = parseInt(totalImagesResult[0].count);

    // Get video count
    const videoCountResult = await sql`
      SELECT COUNT(*) as count FROM videos 
      WHERE camera_id = ${cameraId}
    `;
    const videoCount = parseInt(videoCountResult[0].count);

    // Get recent logs
    const recentLogsResult = await sql`
      SELECT * FROM logs 
      WHERE camera_id = ${cameraId}
      ORDER BY timestamp DESC 
      LIMIT 10
    `;

    return NextResponse.json({
      camera,
      activeTimelapse,
      latestImage,
      stats: {
        currentTimelapseImages: imageCount,
        totalImages,
        videoCount,
        daysSinceFirstCapture: latestImage ? 
          Math.ceil((new Date().getTime() - new Date(latestImage.captured_at).getTime()) / (1000 * 60 * 60 * 24)) : 0
      },
      recentLogs: recentLogsResult
    });

  } catch (error) {
    console.error('Failed to fetch camera details:', error);
    return NextResponse.json({ error: 'Failed to fetch camera details' }, { status: 500 });
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const cameraId = parseInt(id);
    
    if (isNaN(cameraId)) {
      return NextResponse.json({ error: 'Invalid camera ID' }, { status: 400 });
    }

    const body = await request.json();
    const { 
      name, 
      rtsp_url, 
      use_time_window, 
      time_window_start, 
      time_window_end 
    } = body;

    // Validate required fields
    if (!name || !rtsp_url) {
      return NextResponse.json({ 
        error: 'Name and RTSP URL are required' 
      }, { status: 400 });
    }

    // Check if camera exists
    const existingCameraResult = await sql`
      SELECT id FROM cameras WHERE id = ${cameraId}
    `;
    
    if (existingCameraResult.length === 0) {
      return NextResponse.json({ error: 'Camera not found' }, { status: 404 });
    }

    // Update camera
    const updateResult = await sql`
      UPDATE cameras 
      SET 
        name = ${name},
        rtsp_url = ${rtsp_url},
        use_time_window = ${use_time_window || false},
        time_window_start = ${time_window_start || null},
        time_window_end = ${time_window_end || null},
        updated_at = CURRENT_TIMESTAMP
      WHERE id = ${cameraId}
      RETURNING *
    `;

    if (updateResult.length === 0) {
      return NextResponse.json({ error: 'Failed to update camera' }, { status: 500 });
    }

    const updatedCamera = updateResult[0];

    // Broadcast camera updated event
    eventEmitter.emit({
      type: 'camera_updated',
      camera: updatedCamera,
      timestamp: new Date().toISOString()
    })

    return NextResponse.json({
      message: 'Camera updated successfully',
      camera: updatedCamera
    });

  } catch (error) {
    console.error('Failed to update camera:', error);
    return NextResponse.json({ 
      error: 'Failed to update camera' 
    }, { status: 500 });
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const cameraId = parseInt(id);
    
    if (isNaN(cameraId)) {
      return NextResponse.json({ error: 'Invalid camera ID' }, { status: 400 });
    }

    // Check if camera exists
    const existingCameraResult = await sql`
      SELECT name FROM cameras WHERE id = ${cameraId}
    `;
    
    if (existingCameraResult.length === 0) {
      return NextResponse.json({ error: 'Camera not found' }, { status: 404 });
    }

    const cameraName = existingCameraResult[0].name;

    // Delete camera (cascading deletes will handle related records)
    await sql`DELETE FROM cameras WHERE id = ${cameraId}`;

    // Broadcast camera deleted event
    eventEmitter.emit({
      type: 'camera_deleted',
      camera_id: cameraId,
      camera_name: cameraName,
      timestamp: new Date().toISOString()
    })

    return NextResponse.json({
      message: 'Camera deleted successfully',
      deleted_camera: cameraName
    });

  } catch (error) {
    console.error('Failed to delete camera:', error);
    return NextResponse.json({ 
      error: 'Failed to delete camera' 
    }, { status: 500 });
  }
}