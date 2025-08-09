// src/hooks/use-overlay-assets.ts
"use client"

import { useState } from "react"
import { toast } from "sonner"

export interface OverlayAsset {
  id: number
  filename: string
  original_name: string
  file_path: string
  file_size: number
  mime_type: string
  created_at: string
  updated_at: string
}

export interface UseOverlayAssetsReturn {
  assets: OverlayAsset[]
  isLoading: boolean
  error: string | null
  uploadAsset: (file: File, name?: string) => Promise<OverlayAsset | null>
  deleteAsset: (assetId: number) => Promise<boolean>
  refreshAssets: () => Promise<void>
  getAssetUrl: (assetId: number) => string
}

export const useOverlayAssets = (): UseOverlayAssetsReturn => {
  const [assets, setAssets] = useState<OverlayAsset[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refreshAssets = async (): Promise<void> => {
    try {
      setIsLoading(true)
      setError(null)

      const response = await fetch("/api/overlays/assets", {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || "Failed to fetch assets")
      }

      const data = await response.json()
      setAssets(data)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Unknown error"
      setError(errorMessage)
      console.error("Error fetching overlay assets:", err)
    } finally {
      setIsLoading(false)
    }
  }

  const uploadAsset = async (
    file: File,
    name?: string
  ): Promise<OverlayAsset | null> => {
    try {
      setIsLoading(true)
      setError(null)

      console.log("Uploading overlay asset:", file.name)

      const formData = new FormData()
      formData.append("file", file)
      if (name) {
        formData.append("name", name)
      }

      const response = await fetch("/api/overlays/assets/upload", {
        method: "POST",
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || "Failed to upload asset")
      }

      const asset = await response.json()

      // Add to local state
      setAssets((prev) => [...prev, asset])

      toast.success(`✅ Asset uploaded: ${asset.filename}`)
      console.log("Successfully uploaded asset:", asset.filename)

      return asset
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Unknown error"
      setError(errorMessage)
      toast.error(`❌ Upload failed: ${errorMessage}`)
      console.error("Error uploading overlay asset:", err)
      return null
    } finally {
      setIsLoading(false)
    }
  }

  const deleteAsset = async (assetId: number): Promise<boolean> => {
    try {
      setIsLoading(true)
      setError(null)

      console.log("Deleting overlay asset:", assetId)

      const response = await fetch(`/api/overlays/assets/${assetId}`, {
        method: "DELETE",
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || "Failed to delete asset")
      }

      // Remove from local state
      setAssets((prev) => prev.filter((asset) => asset.id !== assetId))

      toast.success("✅ Asset deleted successfully")
      console.log("Successfully deleted asset:", assetId)

      return true
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Unknown error"
      setError(errorMessage)
      toast.error(`❌ Delete failed: ${errorMessage}`)
      console.error("Error deleting overlay asset:", err)
      return false
    } finally {
      setIsLoading(false)
    }
  }

  const getAssetUrl = (assetId: number): string => {
    return `/api/overlays/assets/${assetId}`
  }

  return {
    assets,
    isLoading,
    error,
    uploadAsset,
    deleteAsset,
    refreshAssets,
    getAssetUrl,
  }
}
