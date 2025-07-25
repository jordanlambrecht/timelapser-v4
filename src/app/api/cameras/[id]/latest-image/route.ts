/**
 * Frontend proxy for unified latest camera image metadata endpoint
 *
 * NEW UNIFIED ENDPOINT - Returns complete metadata + URLs for all image variants
 * Replaces multiple separate API calls with single comprehensive response
 */

import { NextRequest } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const cameraId = (await params).id
  return proxyToFastAPI(`/api/cameras/${cameraId}/latest-image`)
}
