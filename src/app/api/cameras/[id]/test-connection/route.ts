// src/app/api/cameras/[id]/test-connection/route.ts
import { NextRequest } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  
  // Proxy to FastAPI backend test connection endpoint
  return proxyToFastAPI(`/api/cameras/${id}/test-connection`, {
    method: "POST",
  })
}
