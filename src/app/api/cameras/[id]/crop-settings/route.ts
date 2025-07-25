// src/app/api/cameras/[id]/crop-settings/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params

  try {
    const cameraId = parseInt(id)
    if (isNaN(cameraId)) {
      return NextResponse.json({ error: "Invalid camera ID" }, { status: 400 })
    }

    // Proxy to FastAPI backend
    return await proxyToFastAPI(`/api/cameras/${cameraId}/crop-settings`, {
      method: "GET",
    })
  } catch (error) {
    console.error("Failed to get camera crop settings:", error)
    return NextResponse.json(
      { error: "Failed to get camera crop settings" },
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
    const cameraId = parseInt(id)
    if (isNaN(cameraId)) {
      return NextResponse.json({ error: "Invalid camera ID" }, { status: 400 })
    }

    const body = await request.json()

    // Proxy to FastAPI backend
    return await proxyToFastAPI(`/api/cameras/${cameraId}/crop-settings`, {
      method: "PUT",
      body,
    })
  } catch (error) {
    console.error("Failed to update camera crop settings:", error)
    return NextResponse.json(
      { error: "Failed to update camera crop settings" },
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
    const cameraId = parseInt(id)
    if (isNaN(cameraId)) {
      return NextResponse.json({ error: "Invalid camera ID" }, { status: 400 })
    }

    // Proxy to FastAPI backend
    return await proxyToFastAPI(`/api/cameras/${cameraId}/crop-settings`, {
      method: "DELETE",
    })
  } catch (error) {
    console.error("Failed to disable camera crop settings:", error)
    return NextResponse.json(
      { error: "Failed to disable camera crop settings" },
      { status: 500 }
    )
  }
}
