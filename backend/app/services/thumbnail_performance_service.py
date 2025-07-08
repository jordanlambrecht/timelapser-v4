# backend/app/services/performance_service.py
"""
Performance Monitoring Service for thumbnail system optimization.

This service collects and analyzes performance metrics to provide insights
for system optimization and scaling decisions.
"""

import psutil
from typing import Dict, List
from datetime import datetime, timedelta
from loguru import logger

from backend.app.utils.timezone_utils import utc_now

from ..database.thumbnail_job_operations import ThumbnailJobOperations
from ..database.sse_events_operations import SSEEventsOperations
from ..constants import (
    THUMBNAIL_QUEUE_SIZE_HIGH_THRESHOLD,
    THUMBNAIL_QUEUE_SIZE_LOW_THRESHOLD,
    THUMBNAIL_PROCESSING_TIME_WARNING_MS,
    THUMBNAIL_MEMORY_WARNING_THRESHOLD,
)


class PerformanceService:
    """
    Service for monitoring and analyzing thumbnail system performance.

    Responsibilities:
    - Collect performance metrics from workers and job queue
    - Analyze system resource usage
    - Provide optimization recommendations
    - Broadcast performance alerts via SSE
    """

    def __init__(
        self,
        thumbnail_job_ops: ThumbnailJobOperations,
        sse_operations: SSEEventsOperations,
    ):
        """
        Initialize PerformanceService.

        Args:
            thumbnail_job_ops: ThumbnailJobOperations for queue metrics
            sse_operations: SSEEventsOperations for performance alerts
        """
        self.thumbnail_job_ops = thumbnail_job_ops
        self.sse_operations = sse_operations
        self.last_metrics_collection = utc_now()
        self.performance_history: List[Dict] = []
        self.max_history_size = 288  # 24 hours at 5-minute intervals

    async def collect_performance_metrics(self) -> Dict:
        """
        Collect comprehensive performance metrics from the system.

        Returns:
            Dictionary containing performance metrics
        """
        try:
            metrics = {
                "timestamp": datetime.utcnow().isoformat(),
                "queue_metrics": await self._get_queue_metrics(),
                "system_metrics": self._get_system_metrics(),
                "worker_metrics": await self._get_worker_metrics(),
            }

            # Store in history for trend analysis
            self.performance_history.append(metrics)

            # Keep only recent history
            if len(self.performance_history) > self.max_history_size:
                self.performance_history = self.performance_history[
                    -self.max_history_size :
                ]

            return metrics

        except Exception as e:
            logger.error(f"Error collecting performance metrics: {e}")
            return {}

    async def _get_queue_metrics(self) -> Dict:
        """Get job queue performance metrics."""
        try:
            stats = await self.thumbnail_job_ops.get_job_statistics()

            return {
                "pending_jobs": stats.get("pending_jobs", 0),
                "processing_jobs": stats.get("processing_jobs", 0),
                "completed_jobs": stats.get("completed_jobs", 0),
                "failed_jobs": stats.get("failed_jobs", 0),
                "total_jobs": stats.get("total_jobs", 0),
                "avg_processing_time_ms": stats.get("avg_processing_time_ms", 0),
                "queue_depth": stats.get("pending_jobs", 0)
                + stats.get("processing_jobs", 0),
            }
        except Exception as e:
            logger.error(f"Error getting queue metrics: {e}")
            return {}

    def _get_system_metrics(self) -> Dict:
        """Get system resource metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_gb = memory.available / (1024**3)

            # Disk usage for data directory
            disk = psutil.disk_usage("/")
            disk_percent = (disk.used / disk.total) * 100
            disk_free_gb = disk.free / (1024**3)

            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "memory_available_gb": round(memory_available_gb, 2),
                "disk_percent": round(disk_percent, 2),
                "disk_free_gb": round(disk_free_gb, 2),
                "load_average": (
                    list(psutil.getloadavg()) if hasattr(psutil, "getloadavg") else None
                ),
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {}

    async def _get_worker_metrics(self) -> Dict:
        """Get worker-specific performance metrics."""
        # This would be enhanced to collect metrics from actual worker instances
        # For now, return placeholder structure
        return {
            "active_workers": 1,  # Would be dynamic based on worker registry
            "high_load_mode": False,  # Would be from worker state
            "concurrent_jobs": 0,  # Would be from worker semaphore
            "batch_size": 10,  # Would be from worker configuration
        }

    async def analyze_performance_trends(self, hours: int = 1) -> Dict:
        """
        Analyze performance trends over the specified time period.

        Args:
            hours: Number of hours to analyze

        Returns:
            Dictionary containing trend analysis
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)

            # Filter recent metrics
            recent_metrics = [
                m
                for m in self.performance_history
                if datetime.fromisoformat(m["timestamp"]) >= cutoff_time
            ]

            if not recent_metrics:
                return {"error": "Insufficient data for trend analysis"}

            # Analyze queue depth trends
            queue_depths = [
                m["queue_metrics"].get("queue_depth", 0) for m in recent_metrics
            ]
            avg_queue_depth = sum(queue_depths) / len(queue_depths)
            max_queue_depth = max(queue_depths)

            # Analyze processing time trends
            processing_times = [
                m["queue_metrics"].get("avg_processing_time_ms", 0)
                for m in recent_metrics
                if m["queue_metrics"].get("avg_processing_time_ms", 0) > 0
            ]
            avg_processing_time = (
                sum(processing_times) / len(processing_times) if processing_times else 0
            )

            # Analyze system resource trends
            cpu_usage = [
                m["system_metrics"].get("cpu_percent", 0) for m in recent_metrics
            ]
            memory_usage = [
                m["system_metrics"].get("memory_percent", 0) for m in recent_metrics
            ]

            avg_cpu = sum(cpu_usage) / len(cpu_usage)
            avg_memory = sum(memory_usage) / len(memory_usage)

            return {
                "period_hours": hours,
                "data_points": len(recent_metrics),
                "queue_analysis": {
                    "avg_queue_depth": round(avg_queue_depth, 2),
                    "max_queue_depth": max_queue_depth,
                    "avg_processing_time_ms": round(avg_processing_time, 2),
                },
                "resource_analysis": {
                    "avg_cpu_percent": round(avg_cpu, 2),
                    "avg_memory_percent": round(avg_memory, 2),
                    "max_cpu_percent": max(cpu_usage),
                    "max_memory_percent": max(memory_usage),
                },
            }

        except Exception as e:
            logger.error(f"Error analyzing performance trends: {e}")
            return {"error": str(e)}

    async def check_performance_alerts(self, metrics: Dict) -> List[Dict]:
        """
        Check for performance issues and generate alerts.

        Args:
            metrics: Current performance metrics

        Returns:
            List of alert dictionaries
        """
        alerts = []

        try:
            queue_metrics = metrics.get("queue_metrics", {})
            system_metrics = metrics.get("system_metrics", {})

            # Check queue depth alerts
            queue_depth = queue_metrics.get("queue_depth", 0)
            if queue_depth >= THUMBNAIL_QUEUE_SIZE_HIGH_THRESHOLD:
                alerts.append(
                    {
                        "type": "queue_high_load",
                        "severity": "warning",
                        "message": f"High queue depth detected: {queue_depth} jobs",
                        "recommendation": "Consider enabling high-load mode or adding more workers",
                        "threshold": THUMBNAIL_QUEUE_SIZE_HIGH_THRESHOLD,
                        "current_value": queue_depth,
                    }
                )

            # Check processing time alerts
            avg_processing_time = queue_metrics.get("avg_processing_time_ms", 0)
            if avg_processing_time > THUMBNAIL_PROCESSING_TIME_WARNING_MS:
                alerts.append(
                    {
                        "type": "slow_processing",
                        "severity": "warning",
                        "message": f"Slow processing detected: {avg_processing_time}ms average",
                        "recommendation": "Check system resources and consider optimizing thumbnail generation",
                        "threshold": THUMBNAIL_PROCESSING_TIME_WARNING_MS,
                        "current_value": avg_processing_time,
                    }
                )

            # Check memory alerts
            memory_percent = system_metrics.get("memory_percent", 0)
            if memory_percent > (THUMBNAIL_MEMORY_WARNING_THRESHOLD * 100):
                alerts.append(
                    {
                        "type": "high_memory_usage",
                        "severity": "warning",
                        "message": f"High memory usage detected: {memory_percent}%",
                        "recommendation": "Consider reducing batch size or concurrent jobs",
                        "threshold": THUMBNAIL_MEMORY_WARNING_THRESHOLD * 100,
                        "current_value": memory_percent,
                    }
                )

            # Check CPU alerts
            cpu_percent = system_metrics.get("cpu_percent", 0)
            if cpu_percent > 90:
                alerts.append(
                    {
                        "type": "high_cpu_usage",
                        "severity": "warning",
                        "message": f"High CPU usage detected: {cpu_percent}%",
                        "recommendation": "System may be under heavy load, consider reducing concurrent processing",
                        "threshold": 90,
                        "current_value": cpu_percent,
                    }
                )

            # Broadcast alerts via SSE
            for alert in alerts:
                await self.sse_operations.create_event(
                    event_type="performance_alert",
                    event_data=alert,
                    priority="normal",
                    source="performance_service",
                )

            return alerts

        except Exception as e:
            logger.error(f"Error checking performance alerts: {e}")
            return []

    async def get_optimization_recommendations(self) -> List[Dict]:
        """
        Generate optimization recommendations based on current performance.

        Returns:
            List of optimization recommendation dictionaries
        """
        try:
            recommendations = []

            # Analyze recent trends
            trends = await self.analyze_performance_trends(hours=1)

            if "error" in trends:
                return []

            queue_analysis = trends.get("queue_analysis", {})
            resource_analysis = trends.get("resource_analysis", {})

            # Queue depth recommendations
            avg_queue_depth = queue_analysis.get("avg_queue_depth", 0)
            if avg_queue_depth > THUMBNAIL_QUEUE_SIZE_HIGH_THRESHOLD:
                recommendations.append(
                    {
                        "category": "queue_optimization",
                        "priority": "high",
                        "title": "Enable High-Load Mode",
                        "description": f"Queue depth averaging {avg_queue_depth}, consider enabling high-load mode",
                        "action": "Increase batch size and reduce worker interval",
                        "expected_impact": "Reduced queue buildup and faster processing",
                    }
                )

            # Processing time recommendations
            avg_processing_time = queue_analysis.get("avg_processing_time_ms", 0)
            if avg_processing_time > THUMBNAIL_PROCESSING_TIME_WARNING_MS:
                recommendations.append(
                    {
                        "category": "processing_optimization",
                        "priority": "medium",
                        "title": "Optimize Image Processing",
                        "description": f"Average processing time {avg_processing_time}ms is above threshold",
                        "action": "Consider reducing image quality or enabling image downscaling",
                        "expected_impact": "Faster thumbnail generation with acceptable quality",
                    }
                )

            # Resource usage recommendations
            avg_memory = resource_analysis.get("avg_memory_percent", 0)
            if avg_memory > 80:
                recommendations.append(
                    {
                        "category": "memory_optimization",
                        "priority": "medium",
                        "title": "Reduce Memory Usage",
                        "description": f"Memory usage averaging {avg_memory}%",
                        "action": "Reduce concurrent jobs or batch size",
                        "expected_impact": "Lower memory pressure and more stable processing",
                    }
                )

            avg_cpu = resource_analysis.get("avg_cpu_percent", 0)
            if avg_cpu > 85:
                recommendations.append(
                    {
                        "category": "cpu_optimization",
                        "priority": "medium",
                        "title": "Reduce CPU Load",
                        "description": f"CPU usage averaging {avg_cpu}%",
                        "action": "Consider reducing concurrent processing or optimizing algorithms",
                        "expected_impact": "Lower system load and improved responsiveness",
                    }
                )

            return recommendations

        except Exception as e:
            logger.error(f"Error generating optimization recommendations: {e}")
            return []
