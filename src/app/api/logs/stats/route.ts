import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET() {
  return proxyToFastAPI("/api/logs/stats", {
    method: "GET",
  })
}
