// src/app/api/corruption/camera/[id]/reset-degraded/route.ts
import { NextRequest } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  // Updated to use singular 'camera' to match backend standard
  return proxyToFastAPI(`/api/corruption/camera/${id}/reset-degraded`, {
    method: "POST",
  })
}
