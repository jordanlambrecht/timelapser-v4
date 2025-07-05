// src/app/api/settings/corruption/route.ts
import { NextRequest, NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(request: NextRequest) {
  const response = await proxyToFastAPI("/api/corruption/settings/")
  
  // Add no-cache headers
  response.headers.set('Cache-Control', 'no-cache, no-store, must-revalidate')
  response.headers.set('Pragma', 'no-cache')
  response.headers.set('Expires', '0')
  
  return response
}

export async function PUT(request: NextRequest) {
  const body = await request.json()
  const response = await proxyToFastAPI("/api/corruption/settings/", {
    method: "PUT",
    body,
  })
  
  // Add no-cache headers
  response.headers.set('Cache-Control', 'no-cache, no-store, must-revalidate')
  response.headers.set('Pragma', 'no-cache')
  response.headers.set('Expires', '0')
  
  return response
}