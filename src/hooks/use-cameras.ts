// src/hooks/use-cameras.ts
"use client"

import { useState, useEffect } from 'react'

interface Camera {
  id: number
  name: string
  status: 'online' | 'offline' | 'error' | 'connecting'
  enabled: boolean
}

interface UseCamerasReturn {
  cameras: Camera[]
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

export const useCameras = (): UseCamerasReturn => {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchCameras = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const response = await fetch('/api/cameras', {
        headers: {
          'Accept': 'application/json',
        },
      })

      if (!response.ok) {
        throw new Error(`Failed to fetch cameras: ${response.status}`)
      }

      const data = await response.json()
      
      // Handle both array response and object with cameras property
      const cameraList = Array.isArray(data) ? data : data.cameras || []
      setCameras(cameraList)
    } catch (err) {
      console.error('Error fetching cameras:', err)
      setError(err instanceof Error ? err.message : 'Failed to fetch cameras')
    } finally {
      setLoading(false)
    }
  }

  const refetch = async () => {
    await fetchCameras()
  }

  useEffect(() => {
    fetchCameras()
  }, [])

  return {
    cameras,
    loading,
    error,
    refetch,
  }
}