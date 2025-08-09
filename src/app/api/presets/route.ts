// src/app/api/presets/route.ts
/**
 * Redirect route for overlay presets API calls.
 *
 * The frontend hooks expect /api/presets but the actual implementation
 * is at /api/overlays/presets. This route provides the redirect.
 */
import { NextRequest, NextResponse } from "next/server"

const OVERLAY_PRESETS_URL = "/api/overlays/presets"

export async function GET(request: NextRequest) {
  // Get query parameters from the original request
  const url = new URL(request.url)
  const searchParams = url.searchParams.toString()
  const redirectUrl = searchParams
    ? `${OVERLAY_PRESETS_URL}?${searchParams}`
    : OVERLAY_PRESETS_URL

  // Redirect to the actual overlay presets endpoint
  return NextResponse.redirect(new URL(redirectUrl, request.url))
}

export async function POST(request: NextRequest) {
  // Forward POST requests to the actual overlay presets endpoint
  const body = await request.json()

  // Create a new request to the overlay presets endpoint
  const response = await fetch(new URL(OVERLAY_PRESETS_URL, request.url), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  })

  const data = await response.json()
  return NextResponse.json(data, { status: response.status })
}

export async function PUT(request: NextRequest) {
  // Forward PUT requests to the actual overlay presets endpoint
  const body = await request.json()

  const response = await fetch(new URL(OVERLAY_PRESETS_URL, request.url), {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  })

  const data = await response.json()
  return NextResponse.json(data, { status: response.status })
}

export async function DELETE(request: NextRequest) {
  // Forward DELETE requests to the actual overlay presets endpoint
  const response = await fetch(new URL(OVERLAY_PRESETS_URL, request.url), {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
    },
  })

  const data = await response.json()
  return NextResponse.json(data, { status: response.status })
}
