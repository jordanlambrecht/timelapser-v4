import { NextRequest } from "next/server"
import { proxyToFastAPIWithQuery } from "@/lib/fastapi-proxy"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  return proxyToFastAPIWithQuery(
    "/api/video-automation/queue/jobs",
    searchParams
  )
}
