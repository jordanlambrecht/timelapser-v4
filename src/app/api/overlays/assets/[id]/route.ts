// src/app/api/overlays/assets/[id]/route.ts
import { NextRequest, NextResponse } from "next/server"

const FASTAPI_URL =
  process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000"

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await context.params
    console.log(`Serving overlay asset: ${id}`)

    const response = await fetch(`${FASTAPI_URL}/api/overlays/assets/${id}`, {
      method: "GET",
    })

    if (!response.ok) {
      if (response.status === 404) {
        return NextResponse.json({ error: "Asset not found" }, { status: 404 })
      }
      console.error(`Backend asset serve endpoint returned ${response.status}`)
      return NextResponse.json(
        { error: "Failed to serve asset" },
        { status: response.status }
      )
    }

    // Get the file content and headers
    const fileBuffer = await response.arrayBuffer()
    const contentType =
      response.headers.get("content-type") || "application/octet-stream"
    const contentDisposition = response.headers.get("content-disposition")

    // Create response with proper headers
    const headers: Record<string, string> = {
      "Content-Type": contentType,
    }

    if (contentDisposition) {
      headers["Content-Disposition"] = contentDisposition
    }

    console.log(`Successfully served overlay asset: ${id}`)
    return new NextResponse(fileBuffer, {
      status: 200,
      headers,
    })
  } catch (error) {
    console.error("Error serving overlay asset:", error)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await context.params
    console.log(`Deleting overlay asset: ${id}`)

    const response = await fetch(`${FASTAPI_URL}/api/overlays/assets/${id}`, {
      method: "DELETE",
    })

    if (!response.ok) {
      if (response.status === 404) {
        return NextResponse.json({ error: "Asset not found" }, { status: 404 })
      }
      console.error(`Backend asset delete endpoint returned ${response.status}`)
      const errorData = await response
        .json()
        .catch(() => ({ detail: "Unknown error" }))
      return NextResponse.json(
        { error: errorData.detail || "Failed to delete asset" },
        { status: response.status }
      )
    }

    const data = await response.json()
    console.log(`Successfully deleted overlay asset: ${id}`)
    return NextResponse.json(data)
  } catch (error) {
    console.error("Error deleting overlay asset:", error)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}
