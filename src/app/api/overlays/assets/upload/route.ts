// src/app/api/overlays/assets/upload/route.ts
import { NextRequest, NextResponse } from "next/server"

const FASTAPI_URL =
  process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000"

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData()
    const file = formData.get("file") as File
    const name = formData.get("name") as string | null

    if (!file) {
      return NextResponse.json({ error: "No file provided" }, { status: 400 })
    }

    console.log(`Uploading overlay asset: ${file.name} (${file.size} bytes)`)

    // Create new FormData for backend
    const backendFormData = new FormData()
    backendFormData.append("file", file)
    if (name) {
      backendFormData.append("name", name)
    }

    const response = await fetch(`${FASTAPI_URL}/api/overlays/assets/upload`, {
      method: "POST",
      body: backendFormData,
    })

    if (!response.ok) {
      console.error(`Backend asset upload endpoint returned ${response.status}`)
      const errorData = await response
        .json()
        .catch(() => ({ detail: "Unknown error" }))
      return NextResponse.json(
        { error: errorData.detail || "Failed to upload asset" },
        { status: response.status }
      )
    }

    const data = await response.json()
    console.log(`Successfully uploaded overlay asset: ${data.filename}`)
    return NextResponse.json(data, { status: 201 })
  } catch (error) {
    console.error("Error uploading overlay asset:", error)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}
