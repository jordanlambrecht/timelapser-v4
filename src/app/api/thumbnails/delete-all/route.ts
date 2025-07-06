// src/app/api/thumbnails/delete-all/route.ts

import { NextRequest, NextResponse } from "next/server"

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"

export async function DELETE(request: NextRequest) {
  try {
    const response = await fetch(`${BACKEND_URL}/api/thumbnails/delete-all`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
      },
    })

    if (!response.ok) {
      console.error("Backend thumbnail deletion failed:", response.statusText)
      return NextResponse.json(
        { 
          success: false, 
          message: `Backend error: ${response.statusText}` 
        },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("Error deleting thumbnails:", error)
    return NextResponse.json(
      { 
        success: false, 
        message: error instanceof Error ? error.message : "Unknown error occurred" 
      },
      { status: 500 }
    )
  }
}