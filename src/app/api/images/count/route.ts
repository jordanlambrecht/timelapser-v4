// src/app/api/images/count/route.ts
import { NextRequest } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(request: NextRequest) {
  const url = new URL(request.url)
  const searchParams = url.searchParams.toString()
  const endpoint = `/api/images/count?${searchParams}`

  return proxyToFastAPI(endpoint, {
    method: "GET",
  })
}
