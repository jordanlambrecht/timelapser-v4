// src/app/api/images/[id]/download/route.ts
import { NextRequest, NextResponse } from "next/server"

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    const imageId = parseInt(id)

    // Validate image ID
    if (isNaN(imageId) || imageId <= 0) {
      return NextResponse.json(
        { error: "Invalid image ID" },
        { status: 400 }
      )
    }

    // Get backend URL with proper precedence
    const fastApiUrl = process.env.FASTAPI_URL || 
                      process.env.NEXT_PUBLIC_FASTAPI_URL || 
                      "http://localhost:8000"
    
    // Validate backend URL format
    if (!fastApiUrl.startsWith('http')) {
      console.error("Invalid FASTAPI_URL configuration:", fastApiUrl)
      return NextResponse.json(
        { error: "Backend configuration error" },
        { status: 500 }
      )
    }
    
    // Pass through size query parameter with validation
    const searchParams = request.nextUrl.searchParams
    const size = searchParams.get('size') || 'full'
    
    // Validate size parameter against known values
    const validSizes = ['full', 'small', 'thumbnail']
    if (!validSizes.includes(size)) {
      return NextResponse.json(
        { error: "Invalid size parameter. Must be: full, small, or thumbnail" },
        { status: 400 }
      )
    }

    // Build backend URL with proper encoding
    const backendUrl = `${fastApiUrl}/api/images/${imageId}/serve?size=${encodeURIComponent(size)}`
    
    // Call backend with timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 30000) // 30 second timeout
    
    try {
      const response = await fetch(backendUrl, {
        signal: controller.signal
      })
      clearTimeout(timeoutId)

      if (!response.ok) {
        if (response.status === 404) {
          return NextResponse.json(
            { error: "Image not found" },
            { status: 404 }
          )
        }
        
        // Try to get JSON error first, fall back to text
        let errorDetails
        try {
          const contentType = response.headers.get('content-type')
          if (contentType && contentType.includes('application/json')) {
            const errorJson = await response.json()
            errorDetails = errorJson.detail || errorJson.message || 'Unknown error'
          } else {
            errorDetails = await response.text()
          }
        } catch {
          errorDetails = 'Failed to read error response'
        }
        
        return NextResponse.json(
          { error: `Backend error: ${response.status}`, details: errorDetails },
          { status: response.status }
        )
      }

      // Get response metadata
      const contentType = response.headers.get("content-type") || "image/jpeg"
      const contentLength = response.headers.get("content-length")
      const contentEncoding = response.headers.get("content-encoding")
      
      // Determine file extension from content type
      const getExtensionFromContentType = (contentType: string): string => {
        if (contentType.includes('png')) return 'png'
        if (contentType.includes('webp')) return 'webp'
        if (contentType.includes('gif')) return 'gif'
        return 'jpg' // default fallback
      }
      
      const extension = getExtensionFromContentType(contentType)
      const filename = `image_${imageId}_${size}.${extension}`

      // Stream the response for better memory efficiency
      const responseHeaders: Record<string, string> = {
        "Content-Type": contentType,
        "Content-Disposition": `attachment; filename="${filename}"`,
        "Cache-Control": "no-cache", // Don't cache downloads
        "X-Image-ID": imageId.toString(),
        "X-Image-Size": size,
      }
      
      // Preserve content length and encoding if available
      if (contentLength) {
        responseHeaders["Content-Length"] = contentLength
      }
      if (contentEncoding) {
        responseHeaders["Content-Encoding"] = contentEncoding
      }

      // Return streaming response
      return new NextResponse(response.body, {
        status: 200,
        headers: responseHeaders,
      })
      
    } catch (fetchError) {
      clearTimeout(timeoutId)
      if (fetchError instanceof Error && fetchError.name === 'AbortError') {
        return NextResponse.json(
          { error: "Request timeout" },
          { status: 504 }
        )
      }
      throw fetchError
    }
    
  } catch (error) {
    console.error("Image download proxy error:", error)
    return NextResponse.json(
      { error: "Failed to download image" },
      { status: 500 }
    )
  }
}
