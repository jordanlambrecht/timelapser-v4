// src/app/api/settings/weather/refresh/route.ts
import { NextResponse } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function POST() {
  return proxyToFastAPI("/api/settings/weather/refresh", {
    method: "POST",
  })
}
