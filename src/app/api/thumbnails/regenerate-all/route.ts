// src/app/api/thumbnails/regenerate-all/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function POST(request: NextRequest) {
  try {
    // Proxy to FastAPI backend with extended timeout for thumbnail regeneration
    // This operation can take a long time when processing many images
    return proxyToFastAPI("/api/thumbnails/regenerate-all", {
      method: "POST",
      timeout: 120000, // 2 minutes timeout for thumbnail regeneration
    })
  } catch (error) {
    console.error("Thumbnail regeneration start error:", error)
    return NextResponse.json(
      { error: "Failed to start thumbnail regeneration" },
      { status: 500 }
    )
  }
}
