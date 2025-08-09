import { useCallback } from "react"
import { toast } from "@/lib/toast"
import { useSSESubscription } from "@/contexts/sse-context"

interface CaptureEventData {
  camera_id: number
  timelapse_id: number
  image_count: number
  day_number: number
  image_id: number
  [key: string]: any
}

/**
 * Global hook for showing toast notifications on successful captures
 * This hook should be used in the root layout or app component to work across all pages
 */
export function useCaptureToast() {
  // Listen for successful image captures globally
  useSSESubscription<CaptureEventData>(
    (event) => event.type === "image_captured",
    useCallback((event) => {
      // Use the existing toast.imageCaptured helper from lib/toast.ts
      // This will show: "📸 Image captured from Camera X" with description
      toast.imageCaptured(`Camera ${event.data.camera_id}`)
    }, [])
  )
}