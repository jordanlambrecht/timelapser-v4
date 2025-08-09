"use client"

import { useCaptureToast } from "@/hooks/use-capture-toast"

/**
 * Global toast provider component that handles all automatic toast notifications
 * This component should be included in the root layout to work across all pages
 */
export function GlobalToastProvider() {
  // Initialize capture toast notifications
  useCaptureToast()

  // This component doesn't render anything, it just sets up global listeners
  return null
}