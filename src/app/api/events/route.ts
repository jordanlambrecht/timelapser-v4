import { NextRequest, NextResponse } from 'next/server'

// Global event emitter for SSE
class EventEmitter {
  private clients: Set<ReadableStreamDefaultController> = new Set()

  addClient(controller: ReadableStreamDefaultController) {
    this.clients.add(controller)
  }

  removeClient(controller: ReadableStreamDefaultController) {
    this.clients.delete(controller)
  }

  emit(data: any) {
    const message = `data: ${JSON.stringify(data)}\n\n`
    this.clients.forEach(controller => {
      try {
        controller.enqueue(new TextEncoder().encode(message))
      } catch (error) {
        // Client disconnected, remove it
        this.clients.delete(controller)
      }
    })
  }

  getClientCount() {
    return this.clients.size
  }
}

// Global event emitter instance
export const eventEmitter = new EventEmitter()

export async function GET(request: NextRequest) {
  // Set up Server-Sent Events
  const stream = new ReadableStream({
    start(controller) {
      // Add this client to the emitter
      eventEmitter.addClient(controller)

      // Send initial connection message
      const welcomeMessage = `data: ${JSON.stringify({
        type: 'connected',
        message: 'SSE connection established',
        timestamp: new Date().toISOString()
      })}\n\n`
      
      controller.enqueue(new TextEncoder().encode(welcomeMessage))

      // Keep connection alive with heartbeat
      const heartbeat = setInterval(() => {
        try {
          const heartbeatMessage = `data: ${JSON.stringify({
            type: 'heartbeat',
            timestamp: new Date().toISOString()
          })}\n\n`
          controller.enqueue(new TextEncoder().encode(heartbeatMessage))
        } catch (error) {
          clearInterval(heartbeat)
          eventEmitter.removeClient(controller)
        }
      }, 30000) // Every 30 seconds

      // Clean up on close
      request.signal?.addEventListener('abort', () => {
        clearInterval(heartbeat)
        eventEmitter.removeClient(controller)
        try {
          controller.close()
        } catch (error) {
          // Already closed
        }
      })
    }
  })

  return new NextResponse(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET',
      'Access-Control-Allow-Headers': 'Cache-Control',
    },
  })
}

// POST endpoint to broadcast events (used by Python worker)
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    
    // Broadcast event to all connected clients
    eventEmitter.emit(body)
    
    return NextResponse.json({ 
      success: true, 
      clients: eventEmitter.getClientCount(),
      event: body
    })
  } catch (error) {
    console.error('Error broadcasting event:', error)
    return NextResponse.json({ error: 'Failed to broadcast event' }, { status: 500 })
  }
}