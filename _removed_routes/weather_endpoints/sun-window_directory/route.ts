// src/app/api/settings/weather/sun-window/route.ts
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET() {
  return proxyToFastAPI("/api/settings/weather/sun-window", {
    method: "GET",
  })
}
