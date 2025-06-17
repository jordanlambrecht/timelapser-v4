// src/app/api/thumbnails/stats/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET() {
  try {
    // Proxy to FastAPI backend
    return proxyToFastAPI("/api/thumbnails/stats")
  } catch (error) {
    console.error("Thumbnail stats error:", error)
    return NextResponse.json(
      { error: "Failed to get thumbnail statistics" },
      { status: 500 }
    )
  }
}
