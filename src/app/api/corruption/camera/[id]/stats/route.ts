// src/app/api/corruption/camera/[id]/stats/route.ts
import { NextRequest } from "next/server"
import { proxyToFastAPIWithQuery } from "@/lib/fastapi-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const { searchParams } = new URL(request.url)
  
  // Updated to use singular 'camera' to match backend standard
  // Forward any query parameters (like days filter)
  return proxyToFastAPIWithQuery(`/api/corruption/camera/${id}/stats`, searchParams)
}
