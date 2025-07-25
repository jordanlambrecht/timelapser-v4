/**
 * Frontend proxy for latest camera image full resolution serving
 *
 * Serves full resolution image for detailed viewing
 */

import { NextRequest } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const cameraId = (await params).id
  return proxyToFastAPI(`/api/cameras/${cameraId}/latest-image/full`)
}
