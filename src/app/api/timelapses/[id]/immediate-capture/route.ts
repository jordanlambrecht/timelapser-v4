import { NextRequest, NextResponse } from "next/server"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const timelapseId = parseInt(id)
    
    if (isNaN(timelapseId)) {
      return NextResponse.json(
        { error: "Invalid timelapse ID" },
        { status: 400 }
      )
    }

    // Proxy to FastAPI backend
    const response = await fetch(
      `${process.env.NEXT_PUBLIC_FASTAPI_URL}/timelapses/${timelapseId}/immediate-capture`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      }
    )

    const data = await response.json()

    if (!response.ok) {
      return NextResponse.json(
        { error: data.detail || "Failed to trigger immediate capture" },
        { status: response.status }
      )
    }

    return NextResponse.json(data)
  } catch (error) {
    console.error("Error triggering immediate capture:", error)
    return NextResponse.json(
      { error: "Failed to trigger immediate capture" },
      { status: 500 }
    )
  }
}
