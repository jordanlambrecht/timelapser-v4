// src/app/api/images/[id]/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const imageId = (await params).id

    // Proxy to FastAPI backend for image metadata
    return proxyToFastAPI(`/api/images/${imageId}`, {
      method: "GET",
    })
  } catch (error) {
    console.error("Get image error:", error)
    return NextResponse.json({ error: "Failed to get image" }, { status: 500 })
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const imageId = (await params).id

    // Proxy to FastAPI backend for image deletion
    return proxyToFastAPI(`/api/images/${imageId}`, {
      method: "DELETE",
    })
  } catch (error) {
    console.error("Delete image error:", error)
    return NextResponse.json(
      { error: "Failed to delete image" },
      { status: 500 }
    )
  }
}
