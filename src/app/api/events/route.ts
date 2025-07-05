// src/app/api/events/route.ts
import { NextRequest, NextResponse } from "next/server"

/**
 * SSE Streaming Proxy - Database-Driven Architecture
 * 
 * This endpoint implements the correct SSE architecture:
 * Services → Database → FastAPI SSE → Next.js Stream Proxy → Frontend
 * 
 * REPLACES the broken HTTP POST pattern:
 * Services → HTTP POST → Next.js → SSE → Frontend
 */

export async function GET(request: NextRequest) {
  console.log("🔗 New SSE connection established via streaming proxy")

  const encoder = new TextEncoder()
  
  // Create streaming response
  const stream = new ReadableStream({
    async start(controller) {
      let isActive = true
      
      // Handle client disconnect
      request.signal.addEventListener("abort", () => {
        console.log("🔌 Frontend SSE client disconnected")
        isActive = false
      })
      
      try {
        // Connect to FastAPI SSE endpoint using fetch with streaming
        const fastApiUrl = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000"
        const backendSSEUrl = `${fastApiUrl}/api/events`
        
        console.log(`📡 Connecting to FastAPI SSE: ${backendSSEUrl}`)
        
        const response = await fetch(backendSSEUrl, {
          headers: {
            'Accept': 'text/event-stream',
            'Cache-Control': 'no-cache',
          },
          // @ts-ignore - Next.js supports streaming but types might not reflect it
          signal: request.signal,
        })
        
        if (!response.ok) {
          throw new Error(`FastAPI SSE connection failed: ${response.status}`)
        }
        
        if (!response.body) {
          throw new Error('No response body from FastAPI SSE')
        }
        
        // Send connection confirmation
        const welcomeMessage = `data: ${JSON.stringify({
          type: "connected",
          data: {
            message: "Database-driven SSE connection established",
            proxy: "next.js",
            backend: "fastapi"
          },
          timestamp: new Date().toISOString(),
        })}\n\n`
        controller.enqueue(encoder.encode(welcomeMessage))
        
        // Stream from FastAPI to client
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        
        while (isActive) {
          try {
            const { done, value } = await reader.read()
            
            if (done) {
              console.log("FastAPI SSE stream ended")
              break
            }
            
            // Forward the chunk directly to the client
            controller.enqueue(value)
            
          } catch (error) {
            if (isActive) {
              console.error("Error reading from FastAPI SSE:", error)
              
              // Send error event to client
              const errorMessage = `data: ${JSON.stringify({
                type: "error",
                data: {
                  message: "Backend SSE connection error",
                  error: String(error)
                },
                timestamp: new Date().toISOString(),
              })}\n\n`
              controller.enqueue(encoder.encode(errorMessage))
            }
            break
          }
        }
        
        reader.releaseLock()
        
      } catch (error) {
        console.error("Failed to establish FastAPI SSE connection:", error)
        
        const failureMessage = `data: ${JSON.stringify({
          type: "error",
          data: {
            message: "Failed to connect to backend SSE endpoint",
            error: String(error)
          },
          timestamp: new Date().toISOString(),
        })}\n\n`
        
        controller.enqueue(encoder.encode(failureMessage))
      } finally {
        if (isActive) {
          controller.close()
        }
      }
    },
  })

  return new NextResponse(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
      "Access-Control-Allow-Origin": 
        process.env.NODE_ENV === "development" 
          ? "*" 
          : request.headers.get("origin") || "",
      "Access-Control-Allow-Methods": "GET",
      "Access-Control-Allow-Headers": "Cache-Control",
      "X-Content-Type-Options": "nosniff",
      "X-Frame-Options": "DENY",
    },
  })
}

/**
 * POST endpoint REMOVED - No longer needed with database-driven architecture
 * 
 * The old HTTP POST pattern violated architectural principles:
 * - Utils layer making HTTP requests (violates pure functions)
 * - Synchronous HTTP in async context (performance bottleneck)
 * - In-memory queues without persistence (data loss)
 * 
 * New architecture: Services write events to database, FastAPI streams from database
 */