import { NextRequest } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function POST(request: NextRequest) {
  const body = await request.json()
  return proxyToFastAPI("/api/video-automation/trigger/manual", {
    method: "POST",
    body,
  })
}
