// src/app/api/dashboard/route.ts
import { NextRequest } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(request: NextRequest) {
  return proxyToFastAPI("/api/dashboard")
}
