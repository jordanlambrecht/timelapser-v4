// FastAPI proxy helper for Next.js API routes
import { NextResponse } from "next/server"

const FASTAPI_BASE_URL =
  process.env.FASTAPI_URL ||
  process.env.NEXT_PUBLIC_FASTAPI_URL ||
  "http://localhost:8000"

export interface ProxyOptions {
  method?: string
  body?: any
  headers?: Record<string, string>
  timeout?: number
}

/**
 * Proxy a request to the FastAPI backend
 */
export async function proxyToFastAPI(
  endpoint: string,
  options: ProxyOptions = {}
): Promise<NextResponse> {
  try {
    const { method = "GET", body, headers = {}, timeout = 30000 } = options

    const fetchOptions: RequestInit = {
      method,
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      signal: AbortSignal.timeout(timeout),
    }

    if (body && method !== "GET" && method !== "HEAD") {
      fetchOptions.body = typeof body === "string" ? body : JSON.stringify(body)
    }

    const url = `${FASTAPI_BASE_URL}${endpoint}`
    console.log(`Proxying ${method} ${url}`)

    const response = await fetch(url, fetchOptions)

    // Handle different response types
    const contentType = response.headers.get("content-type")
    let responseData: any

    if (contentType?.includes("application/json")) {
      responseData = await response.json()
    } else if (contentType?.includes("text/")) {
      responseData = await response.text()
    } else {
      // For binary data or other types
      responseData = await response.arrayBuffer()
    }

    // Forward the status code and response from FastAPI
    // Create headers object from the FastAPI response
    const responseHeaders = new Headers()

    // Copy important headers from the FastAPI response
    // Note: We exclude "content-length" to avoid mismatch errors when response body is processed
    const headersToForward = [
      "content-type",
      "cache-control",
      "pragma",
      "expires",
      "last-modified",
      "etag",
      "content-encoding",
      "content-disposition",
    ]

    headersToForward.forEach((headerName) => {
      const headerValue = response.headers.get(headerName)
      if (headerValue) {
        responseHeaders.set(headerName, headerValue)
      }
    })

    if (contentType?.includes("application/json")) {
      return NextResponse.json(responseData, {
        status: response.status,
        headers: responseHeaders,
      })
    } else {
      return new NextResponse(responseData, {
        status: response.status,
        headers: responseHeaders,
      })
    }
  } catch (error) {
    console.error(`FastAPI proxy error for ${endpoint}:`, error)

    if (
      error instanceof Error &&
      (error.name === "TimeoutError" || error.name === "AbortError")
    ) {
      return NextResponse.json(
        { error: "Backend service timeout" },
        { status: 504 }
      )
    }

    return NextResponse.json(
      { error: "Failed to communicate with backend service" },
      { status: 500 }
    )
  }
}

/**
 * Proxy a request with query parameters
 */
export async function proxyToFastAPIWithQuery(
  endpoint: string,
  searchParams: URLSearchParams,
  options: ProxyOptions = {}
): Promise<NextResponse> {
  const queryString = searchParams.toString()
  const fullEndpoint = queryString ? `${endpoint}?${queryString}` : endpoint
  return proxyToFastAPI(fullEndpoint, options)
}
