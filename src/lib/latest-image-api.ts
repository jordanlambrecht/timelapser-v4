/**
 * API utilities for latest camera image endpoints
 * 
 * Provides low-level functions for interacting with the unified latest-image API
 */

import { LatestImageMetadata, LatestImageResponse } from '@/hooks/use-latest-image'

/**
 * Fetch latest image metadata for a camera
 * 
 * @param cameraId - ID of the camera
 * @returns Promise with latest image data
 */
export async function fetchLatestImageMetadata(
  cameraId: number | string
): Promise<LatestImageMetadata> {
  const response = await fetch(`/api/cameras/${cameraId}/latest-image`)
  const data: LatestImageResponse = await response.json()
  
  if (!response.ok) {
    throw new Error(data.message || `HTTP ${response.status}`)
  }
  
  if (!data.success || !data.data) {
    throw new Error(data.message || 'Failed to fetch latest image metadata')
  }
  
  return data.data
}

/**
 * Get URLs for all latest image variants
 * 
 * @param cameraId - ID of the camera
 * @returns Object with URLs for all image sizes
 */
export function getLatestImageUrls(cameraId: number | string) {
  return {
    metadata: `/api/cameras/${cameraId}/latest-image`,
    full: `/api/cameras/${cameraId}/latest-image/full`,
    small: `/api/cameras/${cameraId}/latest-image/small`,
    thumbnail: `/api/cameras/${cameraId}/latest-image/thumbnail`,
    download: `/api/cameras/${cameraId}/latest-image/download`
  }
}

/**
 * Download latest image for a camera
 * 
 * @param cameraId - ID of the camera
 * @param filename - Optional custom filename
 */
export async function downloadLatestImage(
  cameraId: number | string,
  filename?: string
): Promise<void> {
  try {
    const response = await fetch(`/api/cameras/${cameraId}/latest-image/download`)
    
    if (!response.ok) {
      throw new Error(`Download failed: ${response.status}`)
    }
    
    // Get the blob and filename from response
    const blob = await response.blob()
    const contentDisposition = response.headers.get('content-disposition')
    const defaultFilename = contentDisposition?.match(/filename[^;=\\n]*=((['\"]).*?\\2|[^;\\n]*)/)?.[1]?.replace(/[\"']/g, '') || `camera_${cameraId}_latest.jpg`
    
    // Create download link
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename || defaultFilename
    
    // Trigger download
    document.body.appendChild(link)
    link.click()
    
    // Cleanup
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    
  } catch (error) {
    console.error('Failed to download latest image:', error)
    throw error
  }
}

/**
 * Check if latest image exists for a camera (HEAD request)
 * 
 * @param cameraId - ID of the camera
 * @returns Promise with boolean indicating if image exists
 */
export async function checkLatestImageExists(
  cameraId: number | string
): Promise<boolean> {
  try {
    const response = await fetch(`/api/cameras/${cameraId}/latest-image`, {
      method: 'HEAD'
    })
    return response.ok
  } catch (error) {
    console.error('Failed to check latest image existence:', error)
    return false
  }
}

/**
 * Preload latest image variants for better performance
 * 
 * @param cameraId - ID of the camera
 * @param variants - Which variants to preload (default: ['thumbnail'])
 */
export function preloadLatestImageVariants(
  cameraId: number | string,
  variants: ('thumbnail' | 'small' | 'full')[] = ['thumbnail']
): void {
  const urls = getLatestImageUrls(cameraId)
  
  variants.forEach(variant => {
    const link = document.createElement('link')
    link.rel = 'preload'
    link.as = 'image'
    link.href = urls[variant]
    document.head.appendChild(link)
  })
}
