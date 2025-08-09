// src/app/api/timelapses/[id]/overlays/route.ts
import { NextRequest, NextResponse } from "next/server"

const FASTAPI_URL =
  process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000"

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  try {
    const { id: timelapseId } = await context.params
    console.log(`Fetching overlay configuration for timelapse ${timelapseId}`)

    const response = await fetch(
      `${FASTAPI_URL}/api/overlays/config/${timelapseId}`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      }
    )

    if (!response.ok) {
      if (response.status === 404) {
        // No overlay configuration exists for this timelapse
        return NextResponse.json(null, { status: 404 })
      }
      console.error(
        `Backend overlay config endpoint returned ${response.status}`
      )
      return NextResponse.json(
        { error: "Failed to fetch overlay configuration" },
        { status: response.status }
      )
    }

    const data = await response.json()
    console.log(
      `Successfully fetched overlay configuration for timelapse ${timelapseId}`
    )
    return NextResponse.json(data)
  } catch (error) {
    console.error("Error fetching timelapse overlay configuration:", error)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  try {
    const { id: timelapseId } = await context.params
    const body = await request.json()
    console.log(`Creating overlay configuration for timelapse ${timelapseId}`)

    const response = await fetch(
      `${FASTAPI_URL}/api/overlays/config/${timelapseId}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      }
    )

    if (!response.ok) {
      console.error(`Backend overlay config POST returned ${response.status}`)
      const errorData = await response
        .json()
        .catch(() => ({ detail: "Unknown error" }))
      return NextResponse.json(
        { error: errorData.detail || "Failed to create overlay configuration" },
        { status: response.status }
      )
    }

    const data = await response.json()
    console.log(
      `Successfully created overlay configuration for timelapse ${timelapseId}`
    )
    return NextResponse.json(data, { status: 201 })
  } catch (error) {
    console.error("Error creating timelapse overlay configuration:", error)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ id: string }> }
) {
  try {
    const { id: timelapseId } = await context.params
    const body = await request.json()
    console.log(`Updating overlay configuration for timelapse ${timelapseId}`)

    const response = await fetch(
      `${FASTAPI_URL}/api/overlays/config/${timelapseId}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      }
    )

    if (!response.ok) {
      console.error(`Backend overlay config PUT returned ${response.status}`)
      const errorData = await response
        .json()
        .catch(() => ({ detail: "Unknown error" }))
      return NextResponse.json(
        { error: errorData.detail || "Failed to update overlay configuration" },
        { status: response.status }
      )
    }

    const data = await response.json()
    console.log(
      `Successfully updated overlay configuration for timelapse ${timelapseId}`
    )
    return NextResponse.json(data)
  } catch (error) {
    console.error("Error updating timelapse overlay configuration:", error)
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
    const { id: timelapseId } = await context.params
    console.log(`Deleting overlay configuration for timelapse ${timelapseId}`)

    const response = await fetch(
      `${FASTAPI_URL}/api/overlays/config/${timelapseId}`,
      {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
      }
    )

    if (!response.ok) {
      if (response.status === 404) {
        return NextResponse.json(
          { error: "Overlay configuration not found" },
          { status: 404 }
        )
      }
      console.error(`Backend overlay config DELETE returned ${response.status}`)
      return NextResponse.json(
        { error: "Failed to delete overlay configuration" },
        { status: response.status }
      )
    }

    console.log(
      `Successfully deleted overlay configuration for timelapse ${timelapseId}`
    )
    return NextResponse.json({
      message: "Overlay configuration deleted successfully",
    })
  } catch (error) {
    console.error("Error deleting timelapse overlay configuration:", error)
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    )
  }
}
