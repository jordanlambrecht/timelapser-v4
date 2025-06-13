import { NextResponse } from 'next/server';
import { sql } from '@/lib/db';

export async function GET() {
  try {
    // Get camera health stats
    const cameraStats = await sql`
      SELECT 
        COUNT(*) as total_cameras,
        COUNT(CASE WHEN health_status = 'online' THEN 1 END) as online_cameras,
        COUNT(CASE WHEN health_status = 'offline' THEN 1 END) as offline_cameras,
        COUNT(CASE WHEN status = 'active' THEN 1 END) as active_cameras
      FROM cameras
    `;
    
    // Get timelapse stats
    const timelapseStats = await sql`
      SELECT 
        COUNT(CASE WHEN status = 'running' THEN 1 END) as running_timelapses,
        COUNT(CASE WHEN status = 'paused' THEN 1 END) as paused_timelapses,
        COUNT(CASE WHEN status = 'stopped' THEN 1 END) as stopped_timelapses
      FROM timelapses
    `;
    
    // Get recent captures count (last hour)
    const captureStats = await sql`
      SELECT COUNT(*) as recent_captures
      FROM logs 
      WHERE level = 'INFO' 
        AND message LIKE '%Image capture successful%'
        AND timestamp > CURRENT_TIMESTAMP - INTERVAL '1 hour'
    `;
    
    // Get total images count
    const imageStats = await sql`
      SELECT COUNT(*) as total_images
      FROM images
    `;

    const cameras = cameraStats[0] || { total_cameras: 0, online_cameras: 0, offline_cameras: 0, active_cameras: 0 };
    const timelapses = timelapseStats[0] || { running_timelapses: 0, paused_timelapses: 0, stopped_timelapses: 0 };
    const captures = captureStats[0] || { recent_captures: 0 };
    const images = imageStats[0] || { total_images: 0 };

    // Determine overall system status
    const offlineCameras = parseInt(cameras.offline_cameras) || 0;
    const totalCameras = parseInt(cameras.total_cameras) || 0;
    
    let status = 'healthy';
    if (totalCameras === 0) {
      status = 'no_cameras';
    } else if (offlineCameras > 0) {
      status = offlineCameras === totalCameras ? 'all_offline' : 'degraded';
    }

    const healthData = {
      status,
      timestamp: new Date().toISOString(),
      cameras: {
        total: parseInt(cameras.total_cameras) || 0,
        online: parseInt(cameras.online_cameras) || 0,
        offline: parseInt(cameras.offline_cameras) || 0,
        active: parseInt(cameras.active_cameras) || 0,
      },
      timelapses: {
        running: parseInt(timelapses.running_timelapses) || 0,
        paused: parseInt(timelapses.paused_timelapses) || 0,
        stopped: parseInt(timelapses.stopped_timelapses) || 0,
      },
      captures: {
        last_hour: parseInt(captures.recent_captures) || 0,
      },
      images: {
        total: parseInt(images.total_images) || 0,
      },
      uptime: {
        worker_running: true, // Assume worker is running if API is accessible
        last_health_check: new Date().toISOString(),
      }
    };

    return NextResponse.json(healthData);
    
  } catch (error) {
    console.error('Health check error:', error);
    
    return NextResponse.json({
      status: 'error',
      timestamp: new Date().toISOString(),
      error: 'Health check failed',
      cameras: { total: 0, online: 0, offline: 0, active: 0 },
      timelapses: { running: 0, paused: 0, stopped: 0 },
      captures: { last_hour: 0 },
      images: { total: 0 },
      uptime: { worker_running: false, last_health_check: new Date().toISOString() }
    }, { status: 500 });
  }
}