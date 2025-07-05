// src/app/api/videos/generation-queue/route.ts
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET() {
  return proxyToFastAPI("/api/videos/generation-queue")
}
