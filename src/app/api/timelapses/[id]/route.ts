// src/app/api/timelapses/[id]/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"
import { eventEmitter } from "@/lib/event-emitter"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params

  try {
    // Proxy to FastAPI backend
    const response = await proxyToFastAPI(`/api/timelapses/${id}`)

    if (!response.ok) {
      return NextResponse.json(
        { error: "Timelapse not found" },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("Failed to fetch timelapse:", error)
    return NextResponse.json(
      { error: "Failed to fetch timelapse" },
      { status: 500 }
    )
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params

  try {
    const body = await request.json()

    // Proxy to FastAPI backend
    const response = await proxyToFastAPI(`/api/timelapses/${id}`, {
      method: "PUT",
      body,
    })

    if (!response.ok) {
      const errorData = await response.json()
      return NextResponse.json(
        { error: errorData.detail || "Failed to update timelapse" },
        { status: response.status }
      )
    }

    const data = await response.json()
    
    // Broadcast SSE event for timelapse updates
    eventEmitter.emit({
      type: "timelapse_updated",
      data: {
        timelapse_id: parseInt(id),
        camera_id: data.camera_id,
        updates: body,
      },
      timestamp: new Date().toISOString(),
    })
    
    // Also broadcast specific status change event if status was updated
    if (body.status) {
      eventEmitter.emit({
        type: "timelapse_status_changed",
        data: {
          camera_id: data.camera_id,
          timelapse_id: parseInt(id),
          status: body.status,
        },
        timestamp: new Date().toISOString(),
      })
    }
    
    return NextResponse.json(data)
  } catch (error) {
    console.error("Failed to update timelapse:", error)
    return NextResponse.json(
      { error: "Failed to update timelapse" },
      { status: 500 }
    )
  }
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params

  try {
    const body = await request.json()

    // Proxy to FastAPI backend
    const response = await proxyToFastAPI(`/api/timelapses/${id}`, {
      method: "PATCH",
      body,
    })

    if (!response.ok) {
      const errorData = await response.json()
      return NextResponse.json(
        { error: errorData.detail || "Failed to update timelapse" },
        { status: response.status }
      )
    }

    const data = await response.json()
    
    // Broadcast SSE event for timelapse updates
    eventEmitter.emit({
      type: "timelapse_updated",
      data: {
        timelapse_id: parseInt(id),
        camera_id: data.camera_id,
        updates: body,
      },
      timestamp: new Date().toISOString(),
    })
    
    // Also broadcast specific status change event if status was updated
    if (body.status) {
      eventEmitter.emit({
        type: "timelapse_status_changed",
        data: {
          camera_id: data.camera_id,
          timelapse_id: parseInt(id),
          status: body.status,
        },
        timestamp: new Date().toISOString(),
      })
    }
    
    return NextResponse.json(data)
  } catch (error) {
    console.error("Failed to update timelapse:", error)
    return NextResponse.json(
      { error: "Failed to update timelapse" },
      { status: 500 }
    )
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params

  try {
    // Get timelapse data before deletion for SSE event
    const getResponse = await proxyToFastAPI(`/api/timelapses/${id}`)
    let timelapseData = null
    if (getResponse.ok) {
      timelapseData = await getResponse.json()
    }

    // Proxy to FastAPI backend
    const response = await proxyToFastAPI(`/api/timelapses/${id}`, {
      method: "DELETE",
    })

    if (!response.ok) {
      const errorData = await response.json()
      return NextResponse.json(
        { error: errorData.detail || "Failed to delete timelapse" },
        { status: response.status }
      )
    }

    const data = await response.json()
    
    // Broadcast SSE event for timelapse deletion
    if (timelapseData) {
      eventEmitter.emit({
        type: "timelapse_deleted",
        data: {
          timelapse_id: parseInt(id),
          camera_id: timelapseData.camera_id,
          timelapse_name: timelapseData.name,
        },
        timestamp: new Date().toISOString(),
      })
    }
    
    return NextResponse.json(data)
  } catch (error) {
    console.error("Failed to delete timelapse:", error)
    return NextResponse.json(
      { error: "Failed to delete timelapse" },
      { status: 500 }
    )
  }
}
