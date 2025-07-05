// src/app/api/debug/images/route.ts
import { NextResponse } from "next/server"

export async function GET() {
  try {
    // Proxy to FastAPI backend for secure debug data
    const fastApiUrl =
      process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000"
    const response = await fetch(`${fastApiUrl}/api/images/debug`, {
      method: "GET",
    })

    if (!response.ok) {
      const errorData = await response
        .json()
        .catch(() => ({ error: "Unknown error" }))
      return NextResponse.json(errorData, { status: response.status })
    }

    const debugData = await response.json()
    return NextResponse.json(debugData)
  } catch (error) {
    console.error("Failed to fetch debug info:", error)
    return NextResponse.json(
      { error: "Failed to fetch debug info" },
      { status: 500 }
    )
  }
}
