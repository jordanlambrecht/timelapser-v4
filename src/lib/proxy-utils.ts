/**
 * Shared utilities for image proxy endpoints
 *
 * Handles cache header forwarding, ETag support, and 304 responses
 */

import { NextRequest, NextResponse } from "next/server"

export interface ProxyImageOptions {
  cameraId: string
  endpoint: "thumbnail" | "small" | "full"
  request: NextRequest
  fastApiUrl: string
}

/**
 * Proxy image request to backend with proper cache handling
 *
 * Features:
 * - Forwards If-None-Match and If-Modified-Since headers
 * - Handles 304 Not Modified responses
 * - Preserves ETag and Cache-Control headers from backend
 * - Provides sensible cache defaults based on image type
 */
export async function proxyImageRequest({
  cameraId,
  endpoint,
  request,
  fastApiUrl,
}: ProxyImageOptions): Promise<NextResponse> {
  try {
    // Forward cache validation headers from client
    const clientHeaders: HeadersInit = {}
    const ifNoneMatch = request.headers.get("if-none-match")
    const ifModifiedSince = request.headers.get("if-modified-since")

    if (ifNoneMatch) clientHeaders["If-None-Match"] = ifNoneMatch
    if (ifModifiedSince) clientHeaders["If-Modified-Since"] = ifModifiedSince

    // Call the backend image serving endpoint
    const response = await fetch(
      `${fastApiUrl}/api/cameras/${cameraId}/latest-image/${endpoint}`,
      {
        method: "GET",
        headers: clientHeaders,
      }
    )

    // Handle 304 Not Modified
    if (response.status === 304) {
      return new NextResponse(null, {
        status: 304,
        headers: {
          ETag: response.headers.get("etag") || "",
          "Cache-Control":
            response.headers.get("cache-control") ||
            getDefaultCacheControl(endpoint),
        },
      })
    }

    if (!response.ok) {
      if (response.status === 404) {
        return NextResponse.json(
          { error: "No images found for camera" },
          { status: 404 }
        )
      }

      const errorData = await response.text()
      return NextResponse.json(
        { error: `Backend error: ${response.status}`, details: errorData },
        { status: response.status }
      )
    }

    // Stream the image response
    const imageBuffer = await response.arrayBuffer()
    const contentType = response.headers.get("content-type") || "image/jpeg"

    // Preserve cache headers from backend
    const headers: HeadersInit = {
      "Content-Type": contentType,
      "Content-Length": imageBuffer.byteLength.toString(),
    }

    // Forward cache-related headers from backend
    const cacheControl = response.headers.get("cache-control")
    const etag = response.headers.get("etag")
    const lastModified = response.headers.get("last-modified")

    if (cacheControl) headers["Cache-Control"] = cacheControl
    else headers["Cache-Control"] = getDefaultCacheControl(endpoint)

    if (etag) headers["ETag"] = etag
    if (lastModified) headers["Last-Modified"] = lastModified

    return new NextResponse(imageBuffer, {
      status: 200,
      headers,
    })
  } catch (error) {
    console.error(`Latest image ${endpoint} proxy error:`, error)
    return NextResponse.json(
      { error: `Failed to serve latest image ${endpoint}` },
      { status: 500 }
    )
  }
}

/**
 * Get default cache control header based on image type
 *
 * - Latest images (thumbnails/small/full): 5 minutes
 * - Individual images by ID would be 1 hour (not implemented here)
 */
function getDefaultCacheControl(
  _endpoint: "thumbnail" | "small" | "full"
): string {
  // All latest image variants use 5-minute cache
  return "public, max-age=300, s-maxage=300"
}
