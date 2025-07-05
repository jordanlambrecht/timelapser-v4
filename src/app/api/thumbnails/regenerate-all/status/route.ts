// src/app/api/thumbnails/regenerate-all/status/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET() {
  try {
    // Updated to match backend path format (both use regenerate-all)
    return proxyToFastAPI("/api/thumbnails/regenerate-all/status")
  } catch (error) {
    console.error("Thumbnail regeneration status error:", error)
    return NextResponse.json(
      { error: "Failed to get thumbnail regeneration status" },
      { status: 500 }
    )
  }
}
