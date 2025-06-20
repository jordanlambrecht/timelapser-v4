import { useState } from "react"
import { toast } from "@/lib/toast"

interface DangerZoneActions {
  cleanLogs: () => Promise<void>
  resetSystem: () => Promise<void>
  resetSettings: () => Promise<void>
  deleteAllCameras: () => Promise<void>
  deleteAllImages: () => Promise<void>
  deleteAllTimelapses: () => Promise<void>
  deleteAllThumbnails: () => Promise<void>
  regenerateThumbnails: () => Promise<void>
}

export function useSettingsActions(): DangerZoneActions {
  const [loading, setLoading] = useState(false)

  const performAction = async (
    action: string,
    endpoint: string,
    method: "POST" | "DELETE" = "POST"
  ) => {
    try {
      setLoading(true)

      const response = await fetch(endpoint, {
        method,
        headers: { "Content-Type": "application/json" },
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`Failed to ${action}: ${errorText}`)
      }

      const result = await response.json()
      toast.success(`${action} completed successfully`, {
        description: result.message || `${action} operation finished`,
      })
    } catch (error) {
      console.error(`Failed to ${action}:`, error)
      toast.error(`Failed to ${action}`, {
        description: error instanceof Error ? error.message : "Unknown error",
      })
      throw error
    } finally {
      setLoading(false)
    }
  }

  return {
    cleanLogs: () => performAction("clean logs", "/api/admin/clean-logs"),

    resetSystem: () => performAction("reset system", "/api/admin/reset-system"),

    resetSettings: () =>
      performAction("reset settings", "/api/admin/reset-settings"),

    deleteAllCameras: () =>
      performAction(
        "delete all cameras",
        "/api/admin/delete-cameras",
        "DELETE"
      ),

    deleteAllImages: () =>
      performAction("delete all images", "/api/admin/delete-images", "DELETE"),

    deleteAllTimelapses: () =>
      performAction(
        "delete all timelapses",
        "/api/admin/delete-timelapses",
        "DELETE"
      ),

    deleteAllThumbnails: () =>
      performAction(
        "delete all thumbnails",
        "/api/admin/delete-thumbnails",
        "DELETE"
      ),

    regenerateThumbnails: () =>
      performAction(
        "regenerate thumbnails",
        "/api/admin/regenerate-thumbnails"
      ),
  }
}
