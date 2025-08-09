// src/app/api/weather/route.ts
import { NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET() {
  try {
    console.log("🌤️ Weather API GET request received")

    // Proxy to FastAPI backend weather endpoint
    const response = await proxyToFastAPI("/api/weather")

    // Add no-cache headers for real-time weather data
    response.headers.set("Cache-Control", "no-cache, no-store, must-revalidate")
    response.headers.set("Pragma", "no-cache")
    response.headers.set("Expires", "0")

    console.log(
      `📥 FastAPI weather response: ${response.status} ${response.statusText}`
    )

    return response
  } catch (error) {
    console.error("❌ Weather API error:", error)
    return NextResponse.json(
      {
        error: "Failed to fetch weather data",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    )
  }
}
