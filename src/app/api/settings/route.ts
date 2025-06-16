import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET() {
  // Proxy to FastAPI backend
  return proxyToFastAPI("/api/settings")
}

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json()

    // Proxy to FastAPI backend
    return proxyToFastAPI("/api/settings", {
      method: "PUT",
      body,
    })
  } catch (error) {
    console.error("Settings update error:", error)
    return NextResponse.json(
      { error: "Failed to update settings" },
      { status: 500 }
    )
  }
}
