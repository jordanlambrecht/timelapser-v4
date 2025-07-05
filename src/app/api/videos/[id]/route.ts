// src/app/api/videos/[id]/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params

  // Proxy to FastAPI backend
  return proxyToFastAPI(`/api/videos/${id}`)
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const body = await request.json()

    // Proxy to FastAPI backend
    return proxyToFastAPI(`/api/videos/${id}`, {
      method: "PUT",
      body,
    })
  } catch (error) {
    console.error("Failed to update video:", error)
    return NextResponse.json(
      { error: "Failed to update video" },
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
    
    // Proxy to FastAPI backend - backend handles complete deletion (database + files)
    return proxyToFastAPI(`/api/videos/${id}`, {
      method: "DELETE",
    })
  } catch (error) {
    console.error("Failed to delete video:", error)
    return NextResponse.json(
      { error: "Failed to delete video" },
      { status: 500 }
    )
  }
}
