// src/app/api/corruption/settings/route.ts
import { NextRequest } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(request: NextRequest) {
  return proxyToFastAPI("/api/corruption/settings")
}

export async function PUT(request: NextRequest) {
  const body = await request.json()
  return proxyToFastAPI("/api/corruption/settings", {
    method: "PUT",
    body,
  })
}
