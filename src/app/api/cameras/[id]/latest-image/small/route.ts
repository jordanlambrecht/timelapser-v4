/**
 * Frontend proxy for latest camera image small size serving
 *
 * Serves optimized small-sized image for responsive display
 */

import { NextRequest } from "next/server"
import { proxyImageRequest } from "@/lib/proxy-utils"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const cameraId = (await params).id
  const fastApiUrl = process.env.NEXT_PUBLIC_FASTAPI_URL

  if (!fastApiUrl) {
    throw new Error("FastAPI URL not configured")
  }

  return proxyImageRequest({
    cameraId,
    endpoint: "small",
    request,
    fastApiUrl,
  })
}