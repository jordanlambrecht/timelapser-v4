// src/app/api/settings/[key]/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ key: string }> }
) {
  const { key } = await params

  try {
    if (!key) {
      return NextResponse.json(
        { error: "Setting key is required" },
        { status: 400 }
      )
    }

    // Proxy to FastAPI backend
    const response = await proxyToFastAPI(`/api/settings/${encodeURIComponent(key)}`)

    if (!response.ok) {
      return NextResponse.json(
        { error: "Setting not found" },
        { status: response.status }
      )
    }

    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("Failed to get setting:", error)
    return NextResponse.json(
      {
        error: "Failed to get setting",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    )
  }
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ key: string }> }
) {
  const { key } = await params

  try {
    const body = await request.json()
    
    if (!key) {
      return NextResponse.json(
        { error: "Setting key is required" },
        { status: 400 }
      )
    }

    if (body.value === undefined) {
      return NextResponse.json(
        { error: "Setting value is required" },
        { status: 400 }
      )
    }

    // Proxy to FastAPI backend
    const response = await proxyToFastAPI(`/api/settings/${encodeURIComponent(key)}`, {
      method: "PUT",
      body,
    })

    if (!response.ok) {
      const errorData = await response.json()
      return NextResponse.json(
        { error: errorData.detail || "Failed to update setting" },
        { status: response.status }
      )
    }

    const data = await response.json()

    // Backend already broadcasts SSE event, no need to duplicate here
    return NextResponse.json(data)
  } catch (error) {
    console.error("Failed to update setting:", error)
    return NextResponse.json(
      {
        error: "Failed to update setting",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    )
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ key: string }> }
) {
  const { key } = await params

  try {
    if (!key) {
      return NextResponse.json(
        { error: "Setting key is required" },
        { status: 400 }
      )
    }

    // Proxy to FastAPI backend
    const response = await proxyToFastAPI(`/api/settings/${encodeURIComponent(key)}`, {
      method: "DELETE",
    })

    if (!response.ok) {
      const errorData = await response.json()
      return NextResponse.json(
        { error: errorData.detail || "Failed to delete setting" },
        { status: response.status }
      )
    }

    const data = await response.json()

    // Backend already broadcasts SSE event, no need to duplicate here
    return NextResponse.json(data)
  } catch (error) {
    console.error("Failed to delete setting:", error)
    return NextResponse.json(
      {
        error: "Failed to delete setting",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 }
    )
  }
}
