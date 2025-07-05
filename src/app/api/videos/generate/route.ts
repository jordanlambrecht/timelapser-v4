// src/app/api/videos/generate/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()

    // Proxy to FastAPI backend video generation endpoint
    const response = await proxyToFastAPI("/api/videos/generate", {
      method: "POST",
      body,
    })

    return response
  } catch (error) {
    console.error("Video generation error:", error)
    return NextResponse.json(
      { error: "Failed to generate video" },
      { status: 500 }
    )
  }
}
