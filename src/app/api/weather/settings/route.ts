// src/app/api/weather/settings/route.ts
import { NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET() {
  try {
    console.log("⚙️ Weather settings API GET request received")

    // Proxy to FastAPI backend weather settings endpoint
    const response = await proxyToFastAPI("/api/weather/settings")

    console.log(
      `📥 FastAPI weather settings response: ${response.status} ${response.statusText}`
    )

    return response
  } catch (error) {
    console.error("❌ Weather settings API error:", error)
    return NextResponse.json(
      {
        error: "Failed to fetch weather settings",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    )
  }
}
