// src/app/api/settings/weather/data/route.ts
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET() {
  return proxyToFastAPI("/api/settings/weather/data", {
    method: "GET",
  })
}
