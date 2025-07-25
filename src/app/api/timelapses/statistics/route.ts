// src/app/api/timelapses/statistics/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(request: NextRequest) {
  try {
    // Proxy to FastAPI backend
    const response = await proxyToFastAPI("/api/timelapses/statistics")

    if (!response.ok) {
      return NextResponse.json(
        { error: "Failed to fetch timelapse statistics" },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("Failed to fetch timelapse statistics:", error)
    return NextResponse.json(
      { error: "Failed to fetch timelapse statistics" },
      { status: 500 }
    )
  }
}