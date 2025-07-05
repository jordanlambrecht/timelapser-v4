// src/app/api/logs/cleanup/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

// Import eventEmitter for broadcasting changes
import { eventEmitter } from "@/lib/event-emitter"

export async function DELETE(request: NextRequest) {
  try {
    const url = new URL(request.url)
    const searchParams = url.searchParams.toString()
    
    // Build endpoint with query parameters (days_to_keep)
    const endpoint = searchParams 
      ? `/api/logs/cleanup?${searchParams}` 
      : "/api/logs/cleanup"

    // Proxy delete to FastAPI backend
    const response = await proxyToFastAPI(endpoint, {
      method: "DELETE",
    })

    // If successful, broadcast the event for real-time updates
    if (response.status === 200) {
      // Get the response data from the response body
      const responseText = await response.text()
      const responseData = responseText ? JSON.parse(responseText) : {}

      // Extract cleanup details from response
      const deletedCount = responseData.data?.deleted_count || 0
      const daysKept = responseData.data?.days_kept || 30

      // Broadcast logs cleanup event
      eventEmitter.emit({
        type: "logs_cleanup_completed",
        data: {
          deleted_count: deletedCount,
          days_kept: daysKept,
          cleanup_timestamp: new Date().toISOString(),
        },
        timestamp: new Date().toISOString(),
      })

      // Return the response data
      return NextResponse.json(responseData, { status: response.status })
    }

    return response
  } catch (error) {
    console.error("Failed to cleanup logs:", error)
    return NextResponse.json(
      {
        success: false,
        message: "Failed to cleanup logs",
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    )
  }
}
