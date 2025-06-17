// src/app/api/thumbnails/regenerate-all/cancel/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function POST(request: NextRequest) {
  try {
    // Proxy to FastAPI backend
    return proxyToFastAPI("/api/thumbnails/regenerate-all/cancel", {
      method: "POST",
    })
  } catch (error) {
    console.error("Thumbnail regeneration cancel error:", error)
    return NextResponse.json(
      { error: "Failed to cancel thumbnail regeneration" },
      { status: 500 }
    )
  }
}
