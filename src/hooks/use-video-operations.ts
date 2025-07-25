// src/hooks/use-video-operations.ts
/**
 * Video Operations Hook
 * 
 * Domain: Video (Self-Contained)
 * Responsibilities:
 * - Individual video operations
 * - Video download
 * - Video rename
 * - Video delete
 * - Video metadata access
 * - Video streaming/playback controls
 * 
 * This hook encapsulates all individual video operations according to our
 * domain-driven design where videos are self-contained entities.
 */

import { useCallback, useState } from 'react'
import { toast } from '@/lib/toast'

export interface VideoOperations {
  // Individual video operations
  downloadVideo: (videoId: number, filename?: string) => Promise<boolean>
  deleteVideo: (videoId: number) => Promise<boolean>
  renameVideo: (videoId: number, newName: string) => Promise<boolean>
  getVideoMetadata: (videoId: number) => Promise<VideoMetadata | null>
  
  // Video streaming and playback
  getVideoStreamUrl: (videoId: number) => string
  getVideoThumbnail: (videoId: number) => string
  
  // Video generation status (for individual videos)
  getGenerationStatus: (videoId: number) => Promise<VideoGenerationStatus | null>
  cancelVideoGeneration: (videoId: number) => Promise<boolean>
  
  // Batch individual operations (for selected videos)
  downloadSelectedVideos: (videoIds: number[]) => Promise<boolean>
  deleteSelectedVideos: (videoIds: number[]) => Promise<boolean>
  
  // Video sharing and export
  shareVideo: (videoId: number, options: ShareOptions) => Promise<string | null>
  exportVideo: (videoId: number, format: ExportFormat) => Promise<boolean>
  
  // Loading states
  loading: {
    download: boolean
    delete: boolean
    rename: boolean
    metadata: boolean
    cancel: boolean
    batchDownload: boolean
    batchDelete: boolean
    share: boolean
    export: boolean
  }
}

export interface VideoMetadata {
  id: number
  name: string
  file_path: string
  file_size?: number
  duration?: number
  fps?: number
  width?: number
  height?: number
  codec?: string
  format?: string
  created_at: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  timelapse_id: number
  camera_id: number
  thumbnail_path?: string
  generation_settings?: {
    fps: number
    quality: string
    resolution: string
  }
}

export interface VideoGenerationStatus {
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress?: number
  error_message?: string
  estimated_completion?: string
  processing_stage?: string
}

export interface ShareOptions {
  method: 'link' | 'embed' | 'social'
  permissions?: 'public' | 'private' | 'restricted'
  expiry?: string
}

export interface ExportFormat {
  format: 'mp4' | 'webm' | 'avi' | 'mov'
  quality: 'high' | 'medium' | 'low'
  resolution?: string
  fps?: number
}

export function useVideoOperations(): VideoOperations {
  const [loading, setLoading] = useState({
    download: false,
    delete: false,
    rename: false,
    metadata: false,
    cancel: false,
    batchDownload: false,
    batchDelete: false,
    share: false,
    export: false,
  })

  const setOperationLoading = useCallback((operation: keyof typeof loading, isLoading: boolean) => {
    setLoading(prev => ({ ...prev, [operation]: isLoading }))
  }, [])

  const downloadVideo = useCallback(async (videoId: number, filename?: string): Promise<boolean> => {
    setOperationLoading('download', true)
    try {
      const response = await fetch(`/api/videos/${videoId}/download`)

      if (response.ok) {
        // Handle file download
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = filename || `video-${videoId}.mp4`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)

        toast.success('Video downloaded', {
          description: `Video saved as ${filename || `video-${videoId}.mp4`}`,
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to download video', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to download video', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error downloading video:', error)
      return false
    } finally {
      setOperationLoading('download', false)
    }
  }, [setOperationLoading])

  const deleteVideo = useCallback(async (videoId: number): Promise<boolean> => {
    setOperationLoading('delete', true)
    try {
      const response = await fetch(`/api/videos/${videoId}`, {
        method: 'DELETE',
      })

      if (response.ok) {
        toast.success('Video deleted', {
          description: 'Video has been removed',
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to delete video', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to delete video', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error deleting video:', error)
      return false
    } finally {
      setOperationLoading('delete', false)
    }
  }, [setOperationLoading])

  const renameVideo = useCallback(async (videoId: number, newName: string): Promise<boolean> => {
    setOperationLoading('rename', true)
    try {
      const response = await fetch(`/api/videos/${videoId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName }),
      })

      if (response.ok) {
        toast.success('Video renamed', {
          description: `Video renamed to "${newName}"`,
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to rename video', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to rename video', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error renaming video:', error)
      return false
    } finally {
      setOperationLoading('rename', false)
    }
  }, [setOperationLoading])

  const getVideoMetadata = useCallback(async (videoId: number): Promise<VideoMetadata | null> => {
    setOperationLoading('metadata', true)
    try {
      const response = await fetch(`/api/videos/${videoId}`)
      
      if (response.ok) {
        const data = await response.json()
        return data
      } else {
        console.error('Failed to fetch video metadata:', response.status)
        return null
      }
    } catch (error) {
      console.error('Error fetching video metadata:', error)
      return null
    } finally {
      setOperationLoading('metadata', false)
    }
  }, [setOperationLoading])

  const getVideoStreamUrl = useCallback((videoId: number): string => {
    return `/api/videos/${videoId}/stream`
  }, [])

  const getVideoThumbnail = useCallback((videoId: number): string => {
    return `/api/videos/${videoId}/thumbnail`
  }, [])

  const getGenerationStatus = useCallback(async (videoId: number): Promise<VideoGenerationStatus | null> => {
    try {
      const response = await fetch(`/api/videos/${videoId}/generation-status`)
      
      if (response.ok) {
        const data = await response.json()
        return data
      } else {
        console.error('Failed to fetch video generation status:', response.status)
        return null
      }
    } catch (error) {
      console.error('Error fetching video generation status:', error)
      return null
    }
  }, [])

  const cancelVideoGeneration = useCallback(async (videoId: number): Promise<boolean> => {
    setOperationLoading('cancel', true)
    try {
      const response = await fetch(`/api/videos/${videoId}/cancel-generation`, {
        method: 'POST',
      })

      if (response.ok) {
        toast.success('Video generation cancelled', {
          description: 'Video generation has been stopped',
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to cancel video generation', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to cancel video generation', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error cancelling video generation:', error)
      return false
    } finally {
      setOperationLoading('cancel', false)
    }
  }, [setOperationLoading])

  const downloadSelectedVideos = useCallback(async (videoIds: number[]): Promise<boolean> => {
    if (videoIds.length === 0) {
      toast.error('No videos selected', {
        description: 'Please select videos to download',
        duration: 3000,
      })
      return false
    }

    setOperationLoading('batchDownload', true)
    try {
      const response = await fetch('/api/videos/batch/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_ids: videoIds }),
      })

      if (response.ok) {
        // Handle file download
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `selected-videos-${Date.now()}.zip`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)

        toast.success('Videos downloaded', {
          description: `${videoIds.length} videos downloaded as ZIP file`,
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to download videos', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to download videos', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error downloading selected videos:', error)
      return false
    } finally {
      setOperationLoading('batchDownload', false)
    }
  }, [setOperationLoading])

  const deleteSelectedVideos = useCallback(async (videoIds: number[]): Promise<boolean> => {
    if (videoIds.length === 0) {
      toast.error('No videos selected', {
        description: 'Please select videos to delete',
        duration: 3000,
      })
      return false
    }

    setOperationLoading('batchDelete', true)
    try {
      const response = await fetch('/api/videos/batch/delete', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_ids: videoIds }),
      })

      if (response.ok) {
        toast.success('Videos deleted', {
          description: `${videoIds.length} videos have been removed`,
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to delete videos', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to delete videos', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error deleting selected videos:', error)
      return false
    } finally {
      setOperationLoading('batchDelete', false)
    }
  }, [setOperationLoading])

  const shareVideo = useCallback(async (videoId: number, options: ShareOptions): Promise<string | null> => {
    setOperationLoading('share', true)
    try {
      const response = await fetch(`/api/videos/${videoId}/share`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(options),
      })

      if (response.ok) {
        const data = await response.json()
        toast.success('Share link created', {
          description: 'Video share link has been generated',
          duration: 3000,
        })
        return data.share_url || data.embed_code || null
      } else {
        const error = await response.json()
        toast.error('Failed to create share link', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return null
      }
    } catch (error) {
      toast.error('Failed to create share link', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error sharing video:', error)
      return null
    } finally {
      setOperationLoading('share', false)
    }
  }, [setOperationLoading])

  const exportVideo = useCallback(async (videoId: number, format: ExportFormat): Promise<boolean> => {
    setOperationLoading('export', true)
    try {
      const response = await fetch(`/api/videos/${videoId}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(format),
      })

      if (response.ok) {
        toast.success('Video export started', {
          description: `Exporting video in ${format.format.toUpperCase()} format`,
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to start video export', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to start video export', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error exporting video:', error)
      return false
    } finally {
      setOperationLoading('export', false)
    }
  }, [setOperationLoading])

  return {
    downloadVideo,
    deleteVideo,
    renameVideo,
    getVideoMetadata,
    getVideoStreamUrl,
    getVideoThumbnail,
    getGenerationStatus,
    cancelVideoGeneration,
    downloadSelectedVideos,
    deleteSelectedVideos,
    shareVideo,
    exportVideo,
    loading,
  }
}