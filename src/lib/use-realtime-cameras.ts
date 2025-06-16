// src/lib/use-realtime-cameras.ts
"use client"

import { useEffect, useState, useRef } from "react"
import { CameraWithLastImage } from "./fastapi-client"

export function useRealtimeCameras() {
  const [cameras, setCameras] = useState<CameraWithLastImage[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const eventSourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const fastApiUrl =
      process.env.NEXT_PUBLIC_FASTAPI_URL || "http://localhost:8000"
    const eventSource = new EventSource(`${fastApiUrl}/api/sse/camera-status`)
    eventSourceRef.current = eventSource

    eventSource.onopen = () => {
      console.log("✅ SSE connected for real-time camera updates")
      setIsConnected(true)
    }

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.type === "cameras") {
          setCameras(data.data)
        } else if (data.type === "error") {
          console.error("SSE error:", data.message)
        }
      } catch (error) {
        console.error("Error parsing SSE data:", error)
      }
    }

    eventSource.onerror = (error) => {
      console.error("SSE connection error:", error)
      setIsConnected(false)
    }

    return () => {
      console.log("🔌 Closing SSE connection")
      eventSource.close()
    }
  }, [])

  return {
    cameras,
    isConnected,
    refresh: () => {
      // Force reconnection
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        setTimeout(() => {
          window.location.reload()
        }, 1000)
      }
    },
  }
}
