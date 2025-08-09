// src/app/api/weather/refresh/route.ts
import { NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function POST() {
  try {
    console.log("🔄 Weather refresh API POST request received")

    // Proxy to FastAPI backend weather refresh endpoint
    const response = await proxyToFastAPI("/api/weather/refresh", {
      method: "POST",
    })

    console.log(
      `📥 FastAPI weather refresh response: ${response.status} ${response.statusText}`
    )

    return response
  } catch (error) {
    console.error("❌ Weather refresh API error:", error)
    return NextResponse.json(
      {
        error: "Failed to refresh weather data",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    )
  }
}
