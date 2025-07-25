// src/hooks/use-image-operations.ts
/**
 * Image Operations Hook
 * 
 * Domain: Image (Self-Contained)
 * Responsibilities:
 * - Individual image operations
 * - Image download
 * - Image delete
 * - Image metadata access
 * - Corruption score display
 * - Image variants (thumbnail, small, full)
 * 
 * This hook encapsulates all individual image operations according to our
 * domain-driven design where images are self-contained entities.
 */

import { useCallback, useState } from 'react'
import { toast } from '@/lib/toast'

export interface ImageOperations {
  // Individual image operations
  downloadImage: (imageId: number, filename?: string) => Promise<boolean>
  deleteImage: (imageId: number) => Promise<boolean>
  getImageMetadata: (imageId: number) => Promise<ImageMetadata | null>
  
  // Image variants
  getImageUrl: (imageId: number, variant?: 'full' | 'thumbnail' | 'small') => string
  refreshImageCache: (imageId: number) => void
  
  // Corruption and quality
  flagCorruptedImage: (imageId: number, reason: string) => Promise<boolean>
  unflagImage: (imageId: number) => Promise<boolean>
  
  // Batch individual operations (for selected images)
  downloadSelectedImages: (imageIds: number[]) => Promise<boolean>
  deleteSelectedImages: (imageIds: number[]) => Promise<boolean>
  
  // Loading states
  loading: {
    download: boolean
    delete: boolean
    metadata: boolean
    flag: boolean
    unflag: boolean
    batchDownload: boolean
    batchDelete: boolean
  }
}

export interface ImageMetadata {
  id: number
  file_path: string
  file_size: number | null
  captured_at: string
  day_number: number
  corruption_score?: number
  is_flagged?: boolean
  camera_id: number
  timelapse_id: number
  width?: number
  height?: number
  format?: string
  thumbnail_path?: string
  small_path?: string
}

export function useImageOperations(): ImageOperations {
  const [loading, setLoading] = useState({
    download: false,
    delete: false,
    metadata: false,
    flag: false,
    unflag: false,
    batchDownload: false,
    batchDelete: false,
  })

  const setOperationLoading = useCallback((operation: keyof typeof loading, isLoading: boolean) => {
    setLoading(prev => ({ ...prev, [operation]: isLoading }))
  }, [])

  const downloadImage = useCallback(async (imageId: number, filename?: string): Promise<boolean> => {
    setOperationLoading('download', true)
    try {
      const response = await fetch(`/api/images/${imageId}/download`)

      if (response.ok) {
        // Handle file download
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = filename || `image-${imageId}.jpg`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)

        toast.success('Image downloaded', {
          description: `Image saved as ${filename || `image-${imageId}.jpg`}`,
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to download image', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to download image', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error downloading image:', error)
      return false
    } finally {
      setOperationLoading('download', false)
    }
  }, [setOperationLoading])

  const deleteImage = useCallback(async (imageId: number): Promise<boolean> => {
    setOperationLoading('delete', true)
    try {
      const response = await fetch(`/api/images/${imageId}`, {
        method: 'DELETE',
      })

      if (response.ok) {
        toast.success('Image deleted', {
          description: 'Image has been removed',
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to delete image', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to delete image', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error deleting image:', error)
      return false
    } finally {
      setOperationLoading('delete', false)
    }
  }, [setOperationLoading])

  const getImageMetadata = useCallback(async (imageId: number): Promise<ImageMetadata | null> => {
    setOperationLoading('metadata', true)
    try {
      const response = await fetch(`/api/images/${imageId}`)
      
      if (response.ok) {
        const data = await response.json()
        return data
      } else {
        console.error('Failed to fetch image metadata:', response.status)
        return null
      }
    } catch (error) {
      console.error('Error fetching image metadata:', error)
      return null
    } finally {
      setOperationLoading('metadata', false)
    }
  }, [setOperationLoading])

  const getImageUrl = useCallback((imageId: number, variant: 'full' | 'thumbnail' | 'small' = 'full'): string => {
    switch (variant) {
      case 'thumbnail':
        return `/api/images/${imageId}/thumbnail`
      case 'small':
        return `/api/images/${imageId}/small`
      case 'full':
      default:
        return `/api/images/${imageId}/download`
    }
  }, [])

  const refreshImageCache = useCallback((imageId: number): void => {
    // Force refresh by adding cache-busting parameter
    const timestamp = Date.now()
    const urls = [
      `/api/images/${imageId}/thumbnail`,
      `/api/images/${imageId}/small`,
      `/api/images/${imageId}/download`
    ]
    
    // Preload with cache busting to refresh browser cache
    urls.forEach(url => {
      const img = new Image()
      img.src = `${url}?t=${timestamp}`
    })
  }, [])

  const flagCorruptedImage = useCallback(async (imageId: number, reason: string): Promise<boolean> => {
    setOperationLoading('flag', true)
    try {
      const response = await fetch(`/api/images/${imageId}/flag`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason, is_flagged: true }),
      })

      if (response.ok) {
        toast.success('Image flagged', {
          description: 'Image has been marked as corrupted',
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to flag image', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to flag image', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error flagging image:', error)
      return false
    } finally {
      setOperationLoading('flag', false)
    }
  }, [setOperationLoading])

  const unflagImage = useCallback(async (imageId: number): Promise<boolean> => {
    setOperationLoading('unflag', true)
    try {
      const response = await fetch(`/api/images/${imageId}/flag`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_flagged: false }),
      })

      if (response.ok) {
        toast.success('Image unflagged', {
          description: 'Image corruption flag has been removed',
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to unflag image', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to unflag image', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error unflagging image:', error)
      return false
    } finally {
      setOperationLoading('unflag', false)
    }
  }, [setOperationLoading])

  const downloadSelectedImages = useCallback(async (imageIds: number[]): Promise<boolean> => {
    if (imageIds.length === 0) {
      toast.error('No images selected', {
        description: 'Please select images to download',
        duration: 3000,
      })
      return false
    }

    setOperationLoading('batchDownload', true)
    try {
      const response = await fetch('/api/images/batch/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_ids: imageIds }),
      })

      if (response.ok) {
        // Handle file download
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `selected-images-${Date.now()}.zip`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)

        toast.success('Images downloaded', {
          description: `${imageIds.length} images downloaded as ZIP file`,
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to download images', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to download images', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error downloading selected images:', error)
      return false
    } finally {
      setOperationLoading('batchDownload', false)
    }
  }, [setOperationLoading])

  const deleteSelectedImages = useCallback(async (imageIds: number[]): Promise<boolean> => {
    if (imageIds.length === 0) {
      toast.error('No images selected', {
        description: 'Please select images to delete',
        duration: 3000,
      })
      return false
    }

    setOperationLoading('batchDelete', true)
    try {
      const response = await fetch('/api/images/batch/delete', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_ids: imageIds }),
      })

      if (response.ok) {
        toast.success('Images deleted', {
          description: `${imageIds.length} images have been removed`,
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to delete images', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to delete images', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error deleting selected images:', error)
      return false
    } finally {
      setOperationLoading('batchDelete', false)
    }
  }, [setOperationLoading])

  return {
    downloadImage,
    deleteImage,
    getImageMetadata,
    getImageUrl,
    refreshImageCache,
    flagCorruptedImage,
    unflagImage,
    downloadSelectedImages,
    deleteSelectedImages,
    loading,
  }
}