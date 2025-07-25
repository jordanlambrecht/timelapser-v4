/**
 * Frontend proxy for latest camera image download
 *
 * Downloads latest image with proper filename (e.g., "Camera1_day5_20250630_143022.jpg")
 */

import { NextRequest } from "next/server"
import { proxyToFastAPI } from "@/lib/fastapi-proxy"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const cameraId = (await params).id
  return proxyToFastAPI(`/api/cameras/${cameraId}/latest-image/download`)
}
