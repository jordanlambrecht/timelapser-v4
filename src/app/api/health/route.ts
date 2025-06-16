import { NextResponse } from "next/server"

export async function GET() {
  try {
    // Test database connectivity through FastAPI with timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 5000)

    const fastApiResponse = await fetch("http://localhost:8000/health", {
      signal: controller.signal,
    })

    clearTimeout(timeoutId)

    const isNextjsHealthy = true // Next.js is running if we reach this point
    const isFastApiHealthy = fastApiResponse.ok
    const fastApiData = isFastApiHealthy ? await fastApiResponse.json() : null

    const overallHealthy = isNextjsHealthy && isFastApiHealthy

    return NextResponse.json(
      {
        status: overallHealthy ? "healthy" : "degraded",
        timestamp: new Date().toISOString(),
        services: {
          nextjs: {
            status: "healthy",
            version: process.env.npm_package_version || "unknown",
          },
          fastapi: {
            status: isFastApiHealthy ? "healthy" : "unhealthy",
            data: fastApiData,
          },
        },
        environment: process.env.NODE_ENV,
      },
      { status: overallHealthy ? 200 : 503 }
    )
  } catch (error) {
    return NextResponse.json(
      {
        status: "unhealthy",
        timestamp: new Date().toISOString(),
        error: error instanceof Error ? error.message : "Unknown error",
        services: {
          nextjs: {
            status: "healthy", // Next.js is running if we reach this point
          },
          fastapi: {
            status: "unhealthy",
            error: "Connection failed",
          },
        },
      },
      { status: 503 }
    )
  }
}
