// src/app/api/health/detailed/route.ts
import { NextRequest, NextResponse } from "next/server"

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
  try {
    // Proxy to FastAPI backend for detailed health data
    const fastApiUrl =
      process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000"
    const response = await fetch(`${fastApiUrl}/api/health/detailed`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
      // Add timeout for health checks
      signal: AbortSignal.timeout(10000), // 10 second timeout
    })

    if (!response.ok) {
      const errorData = await response
        .json()
        .catch(() => ({ error: "Health check failed", status: response.status }))
      
      // Return structured error response
      return NextResponse.json(
        {
          success: false,
          message: "Detailed health check failed",
          error: errorData,
          timestamp: new Date().toISOString(),
        },
        { status: response.status }
      )
    }

    const healthData = await response.json()
    
    // Add frontend timestamp for proxy tracking
    const enrichedData = {
      ...healthData,
      proxy_timestamp: new Date().toISOString(),
      source: "fastapi_backend",
    }

    return NextResponse.json(enrichedData)
  } catch (error) {
    console.error("Failed to fetch detailed health data:", error)
    
    // Return comprehensive error response for debugging
    const errorResponse = {
      success: false,
      message: "Failed to fetch detailed health data",
      error: {
        type: error instanceof Error ? error.constructor.name : "UnknownError",
        message: error instanceof Error ? error.message : "Unknown error occurred",
        timestamp: new Date().toISOString(),
      },
      fallback_data: {
        status: "unhealthy",
        checks: {
          frontend_proxy: {
            status: "error",
            error: "Failed to connect to backend health service",
          },
        },
      },
    }

    return NextResponse.json(errorResponse, { status: 503 })
  }
}
