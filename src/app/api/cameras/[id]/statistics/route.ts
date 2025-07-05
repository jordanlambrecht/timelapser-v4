// src/app/api/cameras/[id]/statistics/route.ts
import { NextRequest } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  
  // Proxy to the moved camera statistics endpoint
  // Moved from /api/images/camera/{id}/statistics to /api/cameras/{id}/statistics
  // for better REST architecture - camera statistics belong under cameras namespace
  return proxyToFastAPI(`/api/cameras/${id}/statistics`)
}
