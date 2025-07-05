// src/app/api/logs/sources/route.ts
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET() {
  return proxyToFastAPI("/api/logs/sources", {
    method: "GET",
  })
}
