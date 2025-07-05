// src/app/api/settings/bulk/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    console.log("Bulk settings API POST request received:", body)

    // Validate the request body
    if (!body || typeof body !== "object") {
      console.error("Invalid request body:", body)
      return NextResponse.json(
        { error: "Invalid request body. Expected object with key-value pairs." },
        { status: 400 }
      )
    }

    // Ensure we have at least one setting to update
    const settingsCount = Object.keys(body).length
    if (settingsCount === 0) {
      return NextResponse.json(
        { error: "No settings provided to update" },
        { status: 400 }
      )
    }

    console.log(
      `Proxying to FastAPI: POST /api/settings/bulk with ${settingsCount} settings`
    )

    // Proxy to FastAPI backend
    const response = await proxyToFastAPI("/api/settings/bulk", {
      method: "POST",
      body: { settings: body }, // Wrap in expected Pydantic model structure
    })

    if (!response.ok) {
      const errorData = await response.json()
      return NextResponse.json(
        { error: errorData.detail || "Failed to update settings in bulk" },
        { status: response.status }
      )
    }

    console.log(
      `FastAPI response: ${response.status} ${response.statusText}`
    )

    const data = await response.json()

    // Backend already broadcasts SSE event, no need to duplicate here
    return NextResponse.json(data)
  } catch (error) {
    console.error("Failed to update settings in bulk:", error)
    return NextResponse.json(
      {
        error: "Failed to update settings in bulk",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    )
  }
}
