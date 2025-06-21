// src/app/api/settings/weather/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET() {
  return proxyToFastAPI("/api/settings/weather", {
    method: "GET",
  })
}

export async function PUT(request: NextRequest) {
  const body = await request.json()

  return proxyToFastAPI("/api/settings/weather", {
    method: "PUT",
    body: JSON.stringify(body),
    headers: {
      "Content-Type": "application/json",
    },
  })
}
