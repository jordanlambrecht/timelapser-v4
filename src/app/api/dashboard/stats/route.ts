// src/app/api/dashboard/stats/route.ts
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET() {
  return proxyToFastAPI("/api/dashboard/stats")
}
