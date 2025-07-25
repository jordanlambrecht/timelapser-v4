/**
 * Frontend proxy for latest camera image thumbnail serving
 *
 * Serves 200×150 optimized thumbnail for dashboard display
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
    endpoint: "thumbnail",
    request,
    fastApiUrl,
  })
}
