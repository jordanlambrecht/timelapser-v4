// src/app/api/overlays/assets/route.ts
import { NextRequest, NextResponse } from "next/server"

const FASTAPI_URL =
  process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000"

export async function GET() {
  try {
    console.log("Fetching overlay assets list")

    const response = await fetch(`${FASTAPI_URL}/api/overlays/assets`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    })

    if (!response.ok) {
      console.error(`Backend assets list endpoint returned ${response.status}`)
      const errorData = await response
        .json()
        .catch(() => ({ detail: "Unknown error" }))
      return NextResponse.json(
        { error: errorData.detail || "Failed to fetch assets" },
        { status: response.status }
      )
    }

    const data = await response.json()
    console.log(`Successfully fetched ${data.length || 0} overlay assets`)
    return NextResponse.json(data)
  } catch (error) {
    console.error("Error fetching overlay assets:", error)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}
