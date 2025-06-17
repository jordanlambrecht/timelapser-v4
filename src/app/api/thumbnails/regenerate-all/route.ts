// src/app/api/thumbnails/regenerate-all/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function POST(request: NextRequest) {
  try {
    // Proxy to FastAPI backend
    return proxyToFastAPI("/api/thumbnails/regenerate-all", {
      method: "POST",
    })
  } catch (error) {
    console.error("Thumbnail regeneration start error:", error)
    return NextResponse.json(
      { error: "Failed to start thumbnail regeneration" },
      { status: 500 }
    )
  }
}
