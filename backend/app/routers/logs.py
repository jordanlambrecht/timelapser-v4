# backend/app/routers/logs.py
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any, cast, Tuple
from loguru import logger
from ..database import sync_db

router = APIRouter()


@router.get("/")
def _build_log_query_conditions(
    level: Optional[str], camera_id: Optional[int], search: Optional[str]
) -> Tuple[List[str], List[Any]]:
    """Build WHERE conditions and parameters for log queries"""
    conditions = []
    params = []

    if level and level != "all":
        conditions.append("l.level = %s")
        params.append(level)

    if camera_id:
        conditions.append("l.camera_id = %s")
        params.append(camera_id)

    if search:
        conditions.append("l.message ILIKE %s")
        params.append(f"%{search}%")

    return conditions, params


def _build_log_queries(conditions: List[str]) -> Tuple[str, str]:
    """Build the main query and count query with conditions"""
    base_query = """
        SELECT 
            l.id,
            l.level,
            l.message,
            l.camera_id,
            l.timestamp,
            c.name as camera_name
        FROM logs l
        LEFT JOIN cameras c ON l.camera_id = c.id
    """

    count_query = "SELECT COUNT(*) as total FROM logs l"

    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)
        base_query += where_clause
        count_query += where_clause

    return base_query, count_query


def _format_log_results(logs_result: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format raw log results for API response"""
    return [
        {
            "id": row["id"],
            "level": row["level"],
            "message": row["message"],
            "camera_id": row["camera_id"],
            "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,  # OK: datetime object already timezone-aware from DB
            "camera_name": row["camera_name"],
        }
        for row in logs_result
    ]


async def get_logs(
    level: Optional[str] = Query(None, description="Filter by log level"),
    camera_id: Optional[int] = Query(None, description="Filter by camera ID"),
    search: Optional[str] = Query(None, description="Search in log messages"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
):
    """Get logs with optional filtering and pagination"""
    try:
        offset = (page - 1) * limit

        # Build query conditions
        conditions, params = _build_log_query_conditions(level, camera_id, search)

        # Build queries
        base_query, count_query = _build_log_queries(conditions)

        # Add ordering and pagination to base query
        final_query = base_query + " ORDER BY l.timestamp DESC LIMIT %s OFFSET %s"
        query_params = params + [limit, offset]

        # Execute queries
        with sync_db.get_connection() as conn:
            with conn.cursor() as cur:
                # Get logs
                cur.execute(final_query, query_params)  # type: ignore
                logs_result = cast(List[Dict[str, Any]], cur.fetchall())

                # Get total count
                cur.execute(count_query, params)  # type: ignore
                count_result = cast(Optional[Dict[str, Any]], cur.fetchone())
                total = count_result["total"] if count_result else 0

        # Format results
        logs = _format_log_results(logs_result)

        return {
            "logs": logs,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit,  # Ceiling division
            },
        }

    except Exception as e:
        logger.error("Failed to fetch logs: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch logs") from e


@router.get("/stats")
async def get_log_stats():
    """Get log statistics by level"""
    try:
        query = """
            SELECT 
                level,
                COUNT(*) as count
            FROM logs 
            GROUP BY level
        """

        with sync_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                result = cast(List[Dict[str, Any]], cur.fetchall())

        # Initialize stats
        stats = {"errors": 0, "warnings": 0, "info": 0, "debug": 0, "total": 0}

        # Process results
        total = 0
        for row in result:
            count = int(row["count"])
            total += count

            level = row["level"].lower()
            if level == "error":
                stats["errors"] = count
            elif level in ["warning", "warn"]:
                stats["warnings"] = count
            elif level == "info":
                stats["info"] = count
            elif level == "debug":
                stats["debug"] = count

        stats["total"] = total

        return stats

    except Exception as e:
        logger.error(f"Failed to fetch log stats: {e}")
        return {
            "errors": 0,
            "warnings": 0,
            "info": 0,
            "debug": 0,
            "total": 0,
            "error": str(e),
        }
