// src/app/api/settings/weather/refresh/route.ts
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function POST() {
  return proxyToFastAPI("/api/settings/weather/refresh", {
    method: "POST",
  })
}
