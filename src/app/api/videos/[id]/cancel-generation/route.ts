// src/app/api/videos/[id]/cancel-generation/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    
    const response = await proxyToFastAPI(`/api/videos/${id}/cancel-generation`, {
      method: "POST",
    })

    return response
  } catch (error) {
    console.error("Video cancellation error:", error)
    return NextResponse.json(
      { error: "Failed to cancel video generation" },
      { status: 500 }
    )
  }
}
