// src/app/api/settings/weather/validate-api-key/route.ts
import { NextRequest } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function POST(request: NextRequest) {
  const body = await request.json()

  return proxyToFastAPI("/api/settings/weather/validate-api-key", {
    method: "POST",
    body: JSON.stringify(body),
    headers: {
      "Content-Type": "application/json",
    },
  })
}
