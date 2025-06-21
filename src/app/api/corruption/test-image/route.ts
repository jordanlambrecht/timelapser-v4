import { NextRequest, NextResponse } from "next/server"

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData()
    const image = formData.get('image') as File
    
    if (!image) {
      return NextResponse.json({ error: "No image provided" }, { status: 400 })
    }

    // Validate file type
    if (!image.type.startsWith('image/')) {
      return NextResponse.json({ error: "Invalid file type" }, { status: 400 })
    }

    // Validate file size (10MB max)
    const maxSize = 10 * 1024 * 1024
    if (image.size > maxSize) {
      return NextResponse.json({ error: "File too large" }, { status: 400 })
    }

    // Forward to FastAPI backend
    const backendFormData = new FormData()
    backendFormData.append('image', image)

    const backendResponse = await fetch(
      `${process.env.NEXT_PUBLIC_FASTAPI_URL}/api/corruption/test-image`,
      {
        method: 'POST',
        body: backendFormData,
      }
    )

    if (!backendResponse.ok) {
      const errorText = await backendResponse.text()
      console.error('Backend error:', errorText)
      return NextResponse.json(
        { error: "Failed to analyze image" },
        { status: backendResponse.status }
      )
    }

    const result = await backendResponse.json()
    return NextResponse.json(result)
    
  } catch (error) {
    console.error('Error in corruption test API:', error)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}