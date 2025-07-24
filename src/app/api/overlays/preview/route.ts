// src/app/api/overlays/preview/route.ts
import { NextRequest, NextResponse } from "next/server"

const FASTAPI_URL = process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000"

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    console.log(`Generating overlay preview for camera ${body.camera_id}`)
    
    const response = await fetch(`${FASTAPI_URL}/api/overlays/preview`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      console.error(`Backend overlay preview endpoint returned ${response.status}`)
      const errorData = await response.json().catch(() => ({ detail: "Unknown error" }))
      return NextResponse.json(
        { error: errorData.detail || "Failed to generate overlay preview" },
        { status: response.status }
      )
    }

    const data = await response.json()
    console.log(`Successfully generated overlay preview for camera ${body.camera_id}`)
    return NextResponse.json(data)
  } catch (error) {
    console.error("Error generating overlay preview:", error)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}