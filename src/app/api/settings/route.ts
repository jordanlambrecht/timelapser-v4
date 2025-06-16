// src/app/api/settings/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET() {
  // Proxy to FastAPI backend
  return proxyToFastAPI("/api/settings")
}

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json()
    console.log("🔍 Settings API PUT request received:", body)

    // Validate the request body
    if (!body || typeof body !== "object") {
      console.error("❌ Invalid request body:", body)
      return NextResponse.json(
        { error: "Invalid request body" },
        { status: 400 }
      )
    }

    if (!body.key || body.value === undefined) {
      console.error("❌ Missing key or value in request:", body)
      return NextResponse.json(
        { error: "Missing key or value in request body" },
        { status: 400 }
      )
    }

    console.log(
      `🔄 Proxying to FastAPI: PUT /api/settings with key=${body.key}, value=${body.value}`
    )

    // Proxy to FastAPI backend
    const response = await proxyToFastAPI("/api/settings", {
      method: "PUT",
      body,
    })

    console.log(
      `📥 FastAPI response: ${response.status} ${response.statusText}`
    )

    return response
  } catch (error) {
    console.error("❌ Settings update error:", error)
    return NextResponse.json(
      {
        error: "Failed to update settings",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    )
  }
}
