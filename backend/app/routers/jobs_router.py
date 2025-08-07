"""
Jobs monitoring router for viewing scheduled and running jobs
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
# Scheduler service will be accessed via worker instances
from app.services.logger import get_service_logger
from app.enums import LoggerName, LogSource
from app.database.core import AsyncDatabase
from app.dependencies import get_async_database
from app.database.thumbnail_job_operations import ThumbnailJobOperations
from app.services.overlay_pipeline.services.job_service import AsyncOverlayJobService
from app.database.overlay_job_operations import OverlayJobOperations

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
logger = get_service_logger(LoggerName.API, LogSource.API)

@router.get("/status")
async def get_jobs_status(
    db: AsyncDatabase = Depends(get_async_database)
) -> Dict[str, Any]:
    """
    Get current status of all jobs including scheduled, running, and recent jobs
    """
    try:
        # Get current time in UTC
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Get scheduled jobs from the database
        scheduled_jobs = []
        running_jobs = []
        
        # Get scheduled capture jobs
        scheduled_query = """
            SELECT 
                'capture_' || c.id as id,
                'image_capture' as job_type,
                c.id as camera_id,
                c.name as camera_name,
                'pending' as status,
                c.capture_interval,
                c.next_capture_at as scheduled_time
            FROM cameras c
            WHERE c.is_active = true
                AND c.next_capture_at IS NOT NULL
                AND c.next_capture_at > %s
            ORDER BY c.next_capture_at ASC
            LIMIT 50
        """
        
        async with db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(scheduled_query, (now,))
                scheduled_result = await cur.fetchall()
        
        for row in scheduled_result:
            scheduled_jobs.append({
                "id": row["id"],
                "job_type": row["job_type"],
                "camera_id": row["camera_id"],
                "camera_name": row["camera_name"],
                "status": row["status"],
                "scheduled_time": row["scheduled_time"].isoformat() if row["scheduled_time"] else None,
                "metadata": {"interval": row["capture_interval"]}
            })
        
        # Get running jobs from the database (active capture/video jobs)
        running_query = """
            SELECT 
                'capture_' || c.id as id,
                'image_capture' as job_type,
                c.id as camera_id,
                c.name as camera_name,
                'running' as status,
                c.updated_at as start_time
            FROM cameras c
            WHERE c.is_active = true
            
            UNION ALL
            
            SELECT
                'video_' || t.id as id,
                'video_generation' as job_type,
                t.camera_id,
                c.name as camera_name,
                'running' as status,
                t.updated_at as start_time
            FROM timelapses t
            JOIN cameras c ON t.camera_id = c.id
            WHERE t.is_processing = true
        """
        
        async with db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(running_query)
                running_result = await cur.fetchall()
        
        for row in running_result:
            running_jobs.append({
                "id": row["id"],
                "job_type": row["job_type"],
                "camera_id": row["camera_id"],
                "camera_name": row["camera_name"],
                "status": row["status"],
                "start_time": row["start_time"].isoformat() if row["start_time"] else None
            })
        
        # Get recent completed/failed jobs from logs
        recent_query = """
            SELECT 
                l.id::text as id,
                CASE 
                    WHEN l.message LIKE '%capture%' THEN 'image_capture'
                    WHEN l.message LIKE '%video%' THEN 'video_generation'
                    WHEN l.message LIKE '%thumbnail%' THEN 'thumbnail_generation'
                    ELSE 'unknown'
                END as job_type,
                l.camera_id,
                c.name as camera_name,
                CASE
                    WHEN l.level = 'ERROR' OR l.level = 'CRITICAL' THEN 'failed'
                    ELSE 'completed'
                END as status,
                l.created_at as end_time,
                CASE 
                    WHEN l.level IN ('ERROR', 'CRITICAL') THEN l.message
                    ELSE NULL
                END as error_message
            FROM logs l
            LEFT JOIN cameras c ON l.camera_id = c.id
            WHERE l.created_at >= %s
                AND l.source IN ('WORKER', 'PIPELINE')
                AND (l.message LIKE '%completed%' OR l.message LIKE '%failed%' OR l.level IN ('ERROR', 'CRITICAL'))
            ORDER BY l.created_at DESC
            LIMIT 20
        """
        
        async with db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(recent_query, (today_start,))
                recent_result = await cur.fetchall()
        
        recent_jobs = []
        for row in recent_result:
            recent_jobs.append({
                "id": row["id"],
                "job_type": row["job_type"],
                "camera_id": row["camera_id"],
                "camera_name": row["camera_name"],
                "status": row["status"],
                "end_time": row["end_time"].isoformat() if row["end_time"] else None,
                "error_message": row["error_message"]
            })
        
        # Get statistics
        stats_query = """
            SELECT
                COUNT(CASE WHEN level = 'INFO' AND message LIKE '%completed%' THEN 1 END) as completed_today,
                COUNT(CASE WHEN level IN ('ERROR', 'CRITICAL') THEN 1 END) as failed_today
            FROM logs
            WHERE created_at >= %s
                AND source IN ('WORKER', 'PIPELINE')
        """
        
        async with db.get_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(stats_query, (today_start,))
                stats_result = await cur.fetchone()
        
        # Get thumbnail job statistics
        thumbnail_stats = {}
        try:
            thumbnail_ops = ThumbnailJobOperations(db)
            thumbnail_stats = await thumbnail_ops.get_job_statistics()
        except Exception as e:
            logger.warning(f"Failed to get thumbnail statistics: {str(e)}")
            thumbnail_stats = {
                "total_jobs_24h": 0,
                "pending_jobs": 0,
                "processing_jobs": 0,
                "completed_jobs_24h": 0,
                "failed_jobs_24h": 0,
                "cancelled_jobs_24h": 0,
                "avg_processing_time_ms": 0
            }
        
        # Get overlay job statistics
        overlay_stats = {}
        try:
            overlay_ops = OverlayJobOperations(db)
            overlay_stats_model = await overlay_ops.get_job_statistics()
            # Convert Pydantic model to dictionary
            overlay_stats = overlay_stats_model.model_dump() if overlay_stats_model else {
                "total_jobs_24h": 0,
                "pending_jobs": 0,
                "processing_jobs": 0,
                "completed_jobs_24h": 0,
                "failed_jobs_24h": 0,
                "cancelled_jobs_24h": 0,
                "avg_processing_time_ms": 0
            }
        except Exception as e:
            logger.warning(f"Failed to get overlay statistics: {str(e)}")
            overlay_stats = {
                "total_jobs_24h": 0,
                "pending_jobs": 0,
                "processing_jobs": 0,
                "completed_jobs_24h": 0,
                "failed_jobs_24h": 0,
                "cancelled_jobs_24h": 0,
                "avg_processing_time_ms": 0
            }
        
        return {
            "scheduled": scheduled_jobs,
            "running": running_jobs,
            "recent": recent_jobs,
            "stats": {
                "total_scheduled": len(scheduled_jobs),
                "total_running": len(running_jobs),
                "total_completed_today": stats_result["completed_today"] if stats_result else 0,
                "total_failed_today": stats_result["failed_today"] if stats_result else 0
            },
            "thumbnail_stats": thumbnail_stats,
            "overlay_stats": overlay_stats
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch jobs status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Job cancellation would require direct scheduler access
# This could be implemented later if needed by sending commands
# to the scheduler worker via database or message queue