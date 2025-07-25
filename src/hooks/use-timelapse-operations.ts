// src/hooks/use-timelapse-operations.ts
/**
 * Timelapse Operations Hook
 * 
 * Domain: Timelapse
 * Responsibilities:
 * - All timing & scheduling settings
 * - Image & video generation
 * - Timelapse properties and metadata
 * - Bulk operations (images/videos)
 * - Timelapse lifecycle for ANY timelapse (not just active)
 * - Progress tracking & statistics
 * 
 * This hook encapsulates all timelapse-specific operations according to our
 * domain-driven design where timelapses own their settings and bulk operations.
 */

import { useCallback, useState } from 'react'
import { toast } from '@/lib/toast'

export interface TimelapseOperations {
  // Timelapse CRUD
  createTimelapse: (data: CreateTimelapseData) => Promise<boolean>
  updateTimelapse: (id: number, data: UpdateTimelapseData) => Promise<boolean>
  deleteTimelapse: (id: number) => Promise<boolean>
  
  // Timelapse lifecycle (can operate on ANY timelapse)
  pauseTimelapse: (timelapseId: number) => Promise<boolean>
  resumeTimelapse: (timelapseId: number) => Promise<boolean>
  stopTimelapse: (timelapseId: number) => Promise<boolean>
  
  // Video generation (timelapse domain responsibility)
  generateVideo: (timelapseId: number, config: VideoGenerationConfig) => Promise<boolean>
  getVideoQueue: (timelapseId: number) => Promise<VideoQueueItem[]>
  
  // Bulk operations
  downloadAllImages: (timelapseId: number) => Promise<boolean>
  deleteAllImages: (timelapseId: number, options?: BulkDeleteOptions) => Promise<boolean>
  
  // Statistics and progress
  getTimelapseStats: (timelapseId: number) => Promise<TimelapseStats | null>
  getProgress: (timelapseId: number) => Promise<TimelapseProgress | null>
  
  // Settings management
  updateTimingSettings: (timelapseId: number, settings: TimingSettings) => Promise<boolean>
  updateVideoSettings: (timelapseId: number, settings: VideoSettings) => Promise<boolean>
  
  // Loading states
  loading: {
    create: boolean
    update: boolean
    delete: boolean
    pauseTimelapse: boolean
    resumeTimelapse: boolean
    stopTimelapse: boolean
    generateVideo: boolean
    downloadImages: boolean
    deleteImages: boolean
    updateSettings: boolean
  }
}

export interface CreateTimelapseData {
  camera_id: number
  name: string
  auto_stop_at?: string | null
  time_window_start?: string | null
  time_window_end?: string | null
  use_custom_time_window?: boolean
  capture_interval?: number
}

export interface UpdateTimelapseData {
  name?: string
  auto_stop_at?: string | null
  time_window_start?: string | null
  time_window_end?: string | null
  use_custom_time_window?: boolean
  capture_interval?: number
}

export interface VideoGenerationConfig {
  name: string
  fps?: number
  quality?: 'high' | 'medium' | 'low'
  resolution?: string
  include_overlay?: boolean
}

export interface VideoQueueItem {
  id: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress?: number
  error?: string
  created_at: string
}

export interface BulkDeleteOptions {
  confirm: boolean
  keep_thumbnails?: boolean
  date_range?: {
    start: string
    end: string
  }
}

export interface TimelapseStats {
  total_images: number
  total_videos: number
  total_duration: number
  average_capture_interval: number
  storage_used: number
  corruption_rate?: number
}

export interface TimelapseProgress {
  current_images: number
  estimated_completion?: string
  capture_rate: number
  time_remaining?: number
  status: string
}

export interface TimingSettings {
  capture_interval?: number
  time_window_start?: string | null
  time_window_end?: string | null
  use_custom_time_window?: boolean
  auto_stop_at?: string | null
}

export interface VideoSettings {
  auto_generate?: boolean
  generation_mode?: 'manual' | 'per_capture' | 'scheduled' | 'milestone'
  default_fps?: number
  default_quality?: 'high' | 'medium' | 'low'
  default_resolution?: string
}

export function useTimelapseOperations(): TimelapseOperations {
  const [loading, setLoading] = useState({
    create: false,
    update: false,
    delete: false,
    pauseTimelapse: false,
    resumeTimelapse: false,
    stopTimelapse: false,
    generateVideo: false,
    downloadImages: false,
    deleteImages: false,
    updateSettings: false,
  })

  const setOperationLoading = useCallback((operation: keyof typeof loading, isLoading: boolean) => {
    setLoading(prev => ({ ...prev, [operation]: isLoading }))
  }, [])

  const createTimelapse = useCallback(async (data: CreateTimelapseData): Promise<boolean> => {
    setOperationLoading('create', true)
    try {
      const response = await fetch('/api/timelapses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })

      if (response.ok) {
        toast.success('Timelapse created successfully', {
          description: `Timelapse "${data.name}" has been created`,
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to create timelapse', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to create timelapse', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error creating timelapse:', error)
      return false
    } finally {
      setOperationLoading('create', false)
    }
  }, [setOperationLoading])

  const updateTimelapse = useCallback(async (id: number, data: UpdateTimelapseData): Promise<boolean> => {
    setOperationLoading('update', true)
    try {
      const response = await fetch(`/api/timelapses/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })

      if (response.ok) {
        toast.success('Timelapse updated successfully', {
          description: 'Timelapse settings have been saved',
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to update timelapse', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to update timelapse', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error updating timelapse:', error)
      return false
    } finally {
      setOperationLoading('update', false)
    }
  }, [setOperationLoading])

  const deleteTimelapse = useCallback(async (id: number): Promise<boolean> => {
    setOperationLoading('delete', true)
    try {
      const response = await fetch(`/api/timelapses/${id}`, {
        method: 'DELETE',
      })

      if (response.ok) {
        toast.success('Timelapse deleted successfully', {
          description: 'Timelapse has been removed',
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to delete timelapse', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to delete timelapse', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error deleting timelapse:', error)
      return false
    } finally {
      setOperationLoading('delete', false)
    }
  }, [setOperationLoading])

  const pauseTimelapse = useCallback(async (timelapseId: number): Promise<boolean> => {
    setOperationLoading('pauseTimelapse', true)
    try {
      const response = await fetch(`/api/timelapses/${timelapseId}/pause`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })

      if (response.ok) {
        toast.success('Timelapse paused', {
          description: 'Recording has been paused',
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to pause timelapse', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to pause timelapse', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error pausing timelapse:', error)
      return false
    } finally {
      setOperationLoading('pauseTimelapse', false)
    }
  }, [setOperationLoading])

  const resumeTimelapse = useCallback(async (timelapseId: number): Promise<boolean> => {
    setOperationLoading('resumeTimelapse', true)
    try {
      const response = await fetch(`/api/timelapses/${timelapseId}/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })

      if (response.ok) {
        toast.success('Timelapse resumed', {
          description: 'Recording has been resumed',
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to resume timelapse', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to resume timelapse', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error resuming timelapse:', error)
      return false
    } finally {
      setOperationLoading('resumeTimelapse', false)
    }
  }, [setOperationLoading])

  const stopTimelapse = useCallback(async (timelapseId: number): Promise<boolean> => {
    setOperationLoading('stopTimelapse', true)
    try {
      const response = await fetch(`/api/timelapses/${timelapseId}/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      })

      if (response.ok) {
        toast.success('Timelapse stopped', {
          description: 'Recording has been stopped',
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to stop timelapse', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to stop timelapse', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error stopping timelapse:', error)
      return false
    } finally {
      setOperationLoading('stopTimelapse', false)
    }
  }, [setOperationLoading])

  const generateVideo = useCallback(async (timelapseId: number, config: VideoGenerationConfig): Promise<boolean> => {
    setOperationLoading('generateVideo', true)
    try {
      const response = await fetch(`/api/timelapses/${timelapseId}/generate-video`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      })

      if (response.ok) {
        toast.success('Video generation started', {
          description: `Generating video "${config.name}"`,
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to start video generation', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to start video generation', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error generating video:', error)
      return false
    } finally {
      setOperationLoading('generateVideo', false)
    }
  }, [setOperationLoading])

  const getVideoQueue = useCallback(async (timelapseId: number): Promise<VideoQueueItem[]> => {
    try {
      const response = await fetch(`/api/timelapses/${timelapseId}/video-queue`)
      
      if (response.ok) {
        const data = await response.json()
        return Array.isArray(data) ? data : []
      } else {
        console.error('Failed to fetch video queue:', response.status)
        return []
      }
    } catch (error) {
      console.error('Error fetching video queue:', error)
      return []
    }
  }, [])

  const downloadAllImages = useCallback(async (timelapseId: number): Promise<boolean> => {
    setOperationLoading('downloadImages', true)
    try {
      const response = await fetch(`/api/timelapses/${timelapseId}/images/download`, {
        method: 'POST',
      })

      if (response.ok) {
        // Handle file download
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `timelapse-${timelapseId}-images.zip`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)

        toast.success('Images downloaded', {
          description: 'All images have been downloaded as a ZIP file',
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
      console.error('Error downloading images:', error)
      return false
    } finally {
      setOperationLoading('downloadImages', false)
    }
  }, [setOperationLoading])

  const deleteAllImages = useCallback(async (timelapseId: number, options?: BulkDeleteOptions): Promise<boolean> => {
    setOperationLoading('deleteImages', true)
    try {
      const response = await fetch(`/api/timelapses/${timelapseId}/images/bulk`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(options || { confirm: true }),
      })

      if (response.ok) {
        toast.success('Images deleted', {
          description: 'All images have been removed',
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
      console.error('Error deleting images:', error)
      return false
    } finally {
      setOperationLoading('deleteImages', false)
    }
  }, [setOperationLoading])

  const getTimelapseStats = useCallback(async (timelapseId: number): Promise<TimelapseStats | null> => {
    try {
      const response = await fetch(`/api/timelapses/${timelapseId}/statistics`)
      
      if (response.ok) {
        return await response.json()
      } else {
        console.error('Failed to fetch timelapse stats:', response.status)
        return null
      }
    } catch (error) {
      console.error('Error fetching timelapse stats:', error)
      return null
    }
  }, [])

  const getProgress = useCallback(async (timelapseId: number): Promise<TimelapseProgress | null> => {
    try {
      const response = await fetch(`/api/timelapses/${timelapseId}/progress`)
      
      if (response.ok) {
        return await response.json()
      } else {
        console.error('Failed to fetch timelapse progress:', response.status)
        return null
      }
    } catch (error) {
      console.error('Error fetching timelapse progress:', error)
      return null
    }
  }, [])

  const updateTimingSettings = useCallback(async (timelapseId: number, settings: TimingSettings): Promise<boolean> => {
    setOperationLoading('updateSettings', true)
    try {
      const response = await fetch(`/api/timelapses/${timelapseId}/timing`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      })

      if (response.ok) {
        toast.success('Timing settings updated', {
          description: 'Timelapse timing has been configured',
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to update timing settings', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to update timing settings', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error updating timing settings:', error)
      return false
    } finally {
      setOperationLoading('updateSettings', false)
    }
  }, [setOperationLoading])

  const updateVideoSettings = useCallback(async (timelapseId: number, settings: VideoSettings): Promise<boolean> => {
    setOperationLoading('updateSettings', true)
    try {
      const response = await fetch(`/api/timelapses/${timelapseId}/video-settings`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      })

      if (response.ok) {
        toast.success('Video settings updated', {
          description: 'Video generation settings have been configured',
          duration: 3000,
        })
        return true
      } else {
        const error = await response.json()
        toast.error('Failed to update video settings', {
          description: error.detail || 'Unknown error occurred',
          duration: 5000,
        })
        return false
      }
    } catch (error) {
      toast.error('Failed to update video settings', {
        description: 'Network error or server unavailable',
        duration: 5000,
      })
      console.error('Error updating video settings:', error)
      return false
    } finally {
      setOperationLoading('updateSettings', false)
    }
  }, [setOperationLoading])

  return {
    createTimelapse,
    updateTimelapse,
    deleteTimelapse,
    pauseTimelapse,
    resumeTimelapse,
    stopTimelapse,
    generateVideo,
    getVideoQueue,
    downloadAllImages,
    deleteAllImages,
    getTimelapseStats,
    getProgress,
    updateTimingSettings,
    updateVideoSettings,
    loading,
  }
}