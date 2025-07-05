// src/app/api/cameras/[id]/details/route.ts
import { NextRequest } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  
  // Proxy to FastAPI backend camera details endpoint
  return proxyToFastAPI(`/api/cameras/${id}/details`)
}
