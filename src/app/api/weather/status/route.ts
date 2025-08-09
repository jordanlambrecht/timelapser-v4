// src/app/api/weather/status/route.ts
import { NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET() {
  try {
    console.log("📊 Weather status API GET request received")

    // Proxy to FastAPI backend weather status endpoint
    const response = await proxyToFastAPI("/api/weather/status")

    console.log(
      `📥 FastAPI weather status response: ${response.status} ${response.statusText}`
    )

    return response
  } catch (error) {
    console.error("❌ Weather status API error:", error)
    return NextResponse.json(
      {
        error: "Failed to fetch weather status",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    )
  }
}
