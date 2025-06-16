import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

// Import eventEmitter for broadcasting changes
import { eventEmitter } from "@/app/api/events/route"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params

  return proxyToFastAPI(`/api/cameras/${id}`)
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const body = await request.json()

    // Proxy to FastAPI backend
    const response = await proxyToFastAPI(`/api/cameras/${id}`, {
      method: "PUT",
      body,
    })

    // If successful, broadcast the event
    if (response.status === 200) {
      // Get the response data from the response body
      const responseText = await response.text()
      const responseData = responseText ? JSON.parse(responseText) : {}

      // Broadcast camera updated event
      console.log("Broadcasting camera_updated event:", responseData)
      eventEmitter.emit({
        type: "camera_updated",
        camera: responseData,
        timestamp: new Date().toISOString(),
      })

      // Return the response data
      return NextResponse.json(responseData, { status: response.status })
    }

    return response
  } catch (error) {
    console.error("Failed to update camera:", error)
    return NextResponse.json(
      {
        error: "Failed to update camera",
      },
      { status: 500 }
    )
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params

    // Get camera name before deletion for the event
    const cameraResponse = await proxyToFastAPI(`/api/cameras/${id}`)
    let cameraName = "Unknown Camera"

    if (cameraResponse.status === 200) {
      const cameraText = await cameraResponse.text()
      const cameraData = cameraText ? JSON.parse(cameraText) : {}
      cameraName = cameraData.name || "Unknown Camera"
    }

    // Proxy delete to FastAPI backend
    const response = await proxyToFastAPI(`/api/cameras/${id}`, {
      method: "DELETE",
    })

    // If successful, broadcast the event
    if (response.status === 200 || response.status === 204) {
      // Broadcast camera deleted event
      console.log(
        "Broadcasting camera_deleted event for camera ID:",
        parseInt(id)
      )
      eventEmitter.emit({
        type: "camera_deleted",
        camera_id: parseInt(id),
        camera_name: cameraName,
        timestamp: new Date().toISOString(),
      })
    }

    return response
  } catch (error) {
    console.error("Failed to delete camera:", error)
    return NextResponse.json(
      {
        error: "Failed to delete camera",
      },
      { status: 500 }
    )
  }
}
