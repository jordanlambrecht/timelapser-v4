// src/app/api/health/detailed/route.ts
import { NextRequest } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

/**
 * Frontend proxy for detailed health endpoint
 *
 * Provides comprehensive system monitoring data including:
 * - System resources (CPU, memory, disk usage)
 * - Database performance (connection latency, pool stats)
 * - Application metrics (cameras, timelapses, queue status)
 * - Dependencies (FFmpeg availability)
 * - Storage health and filesystem status
 */
export async function GET(request: NextRequest) {
  return proxyToFastAPI("/api/health/detailed", {
    timeout: 10000, // 10 second timeout for health checks
  })
}
