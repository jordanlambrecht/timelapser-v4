import { NextRequest } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  return proxyToFastAPI(`/api/timelapses/${id}/thumbnails/regenerate`, {
    method: "POST",
  })
}
