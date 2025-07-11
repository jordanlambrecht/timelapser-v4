// src/app/api/videos/[id]/download/route.ts
import { NextRequest } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return proxyToFastAPI(`/api/videos/${id}/download`)
}
