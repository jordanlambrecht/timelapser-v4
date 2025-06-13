"use client"

import { useState, useEffect } from "react"
import {
  Search,
  FunnelIcon,
  X,
  RotateCw,
  TriangleAlert,
  CircleAlert,
  Bug,
  Sigma,
} from "lucide-react"

interface Log {
  id: number
  level: string
  message: string
  camera_id: number | null
  camera_name: string | null
  timestamp: string
}

interface Camera {
  id: number
  name: string
}

interface LogStats {
  errors: number
  warnings: number
  info: number
  debug: number
  total: number
}

export default function LogsPage() {
  const [logs, setLogs] = useState<Log[]>([])
  const [cameras, setCameras] = useState<Camera[]>([])
  const [stats, setStats] = useState<LogStats>({
    errors: 0,
    warnings: 0,
    info: 0,
    debug: 0,
    total: 0,
  })
  const [loading, setLoading] = useState(true)

  // Filter states
  const [filters, setFilters] = useState({
    search: "",
    level: "all",
    source: "all",
    camera: "all",
  })

  const [showFilters, setShowFilters] = useState(true)

  // Fetch cameras for filter dropdown
  useEffect(() => {
    fetchCameras()
  }, [])

  // Fetch logs and stats when filters change
  useEffect(() => {
    fetchLogs()
    fetchStats()
  }, [filters])

  const fetchCameras = async () => {
    try {
      const response = await fetch("/api/cameras")
      const data = await response.json()
      setCameras(Array.isArray(data) ? data : [])
    } catch (error) {
      console.error("Failed to fetch cameras:", error)
      setCameras([])
    }
  }

  const fetchStats = async () => {
    try {
      const response = await fetch("/api/logs/stats")
      if (response.ok) {
        const data = await response.json()
        setStats(data)
      }
    } catch (error) {
      console.error("Failed to fetch log stats:", error)
    }
  }

  const fetchLogs = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()

      if (filters.level !== "all") params.set("level", filters.level)
      if (filters.camera !== "all") params.set("camera_id", filters.camera)
      if (filters.search.trim()) params.set("search", filters.search.trim())

      const response = await fetch(`/api/logs?${params.toString()}`)

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()

      // Handle different response structures
      if (data && data.logs) {
        setLogs(Array.isArray(data.logs) ? data.logs : [])
      } else if (Array.isArray(data)) {
        setLogs(data)
      } else {
        console.error("Unexpected response structure:", data)
        setLogs([])
      }
    } catch (error) {
      console.error("Failed to fetch logs:", error)
      setLogs([])
    } finally {
      setLoading(false)
    }
  }

  const handleFilterChange = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  const clearFilters = () => {
    setFilters({
      search: "",
      level: "all",
      source: "all",
      camera: "all",
    })
  }

  const hasActiveFilters = Object.values(filters).some(
    (value) => value !== "all" && value !== ""
  )

  const getLogLevelColor = (level: string) => {
    switch (level.toLowerCase()) {
      case "error":
        return "text-red-600 bg-red-50 border-red-200"
      case "warning":
      case "warn":
        return "text-yellow bg-yellow/50 border-yellow"
      case "info":
        return "text-blue-600 bg-blue-50 border-blue-200"
      case "debug":
        return "text-gray-600 bg-gray-50 border-gray-200"
      default:
        return "text-gray-600 bg-gray-50 border-gray-200"
    }
  }

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    })
  }

  const getCameraDisplay = (log: Log) => {
    if (log.camera_name) return log.camera_name
    if (log.camera_id) return `Camera ${log.camera_id}`
    return "System"
  }

  const getSourceIcon = (log: Log) => {
    if (log.camera_id) return "📹"
    return "⚙️"
  }

  return (
    <div className='min-h-screen bg-gray-900'>
      <div className='px-4 py-8 mx-auto max-w-7xl sm:px-6 lg:px-8'>
        {/* Header */}
        <div className='mb-8'>
          <h1 className='mb-2 text-3xl font-bold text-white'>System Logs</h1>
          <p className='text-gray-400'>
            Monitor system events, errors, and application activity
          </p>
        </div>

        {/* Stats Cards */}
        <div className='grid grid-cols-2 gap-4 mb-8 md:grid-cols-5'>
          <div className='p-6 bg-gray-800 border border-gray-700 rounded-lg'>
            <div className='flex items-center'>
              <div className='flex-shrink-0'>
                <CircleAlert className='w-8 h-8 text-red-400' />
              </div>
              <div className='ml-4'>
                <div className='text-2xl font-bold text-red-400'>
                  {stats.errors}
                </div>
                <div className='text-sm text-gray-400'>Errors</div>
              </div>
            </div>
          </div>

          <div className='p-6 bg-gray-800 border border-gray-700 rounded-lg'>
            <div className='flex items-center'>
              <div className='flex-shrink-0'>
                <TriangleAlert className='w-8 h-8 text-yellow-400' />
              </div>
              <div className='ml-4'>
                <div className='text-2xl font-bold text-yellow-400'>
                  {stats.warnings}
                </div>
                <div className='text-sm text-gray-400'>Warnings</div>
              </div>
            </div>
          </div>

          <div className='p-6 bg-gray-800 border border-gray-700 rounded-lg'>
            <div className='flex items-center'>
              <div className='flex-shrink-0'>
                <CircleAlert className='w-8 h-8 text-blue-400' />
              </div>
              <div className='ml-4'>
                <div className='text-2xl font-bold text-blue-400'>
                  {stats.info}
                </div>
                <div className='text-sm text-gray-400'>Info</div>
              </div>
            </div>
          </div>

          <div className='p-6 bg-gray-800 border border-gray-700 rounded-lg'>
            <div className='flex items-center'>
              <div className='flex-shrink-0'>
                <Bug className='w-8 h-8 text-gray-400' />
              </div>
              <div className='ml-4'>
                <div className='text-2xl font-bold text-gray-400'>
                  {stats.debug}
                </div>
                <div className='text-sm text-gray-400'>Debug</div>
              </div>
            </div>
          </div>

          <div className='p-6 bg-gray-800 border border-gray-700 rounded-lg'>
            <div className='flex items-center'>
              <div className='flex-shrink-0'>
                <div className='flex-shrink-0'>
                  <Sigma className='w-8 h-8 text-cyan' />
                </div>
              </div>
              <div className='ml-4'>
                <div className='text-2xl font-bold text-white'>
                  {stats.total}
                </div>
                <div className='text-sm text-gray-400'>Total Logs</div>
              </div>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className='p-6 mb-6 bg-gray-800 border border-gray-700 rounded-lg'>
          <div className='flex items-center justify-between mb-4'>
            <div className='flex items-center'>
              <FunnelIcon className='w-5 h-5 mr-2 text-gray-400' />
              <h3 className='text-lg font-medium text-white'>Filters</h3>
            </div>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className='text-gray-400 hover:text-white'
            >
              {showFilters ? "Hide" : "Show"}
            </button>
          </div>

          {showFilters && (
            <div className='space-y-4'>
              {/* Search */}
              <div>
                <label className='block mb-2 text-sm font-medium text-gray-300'>
                  Search
                </label>
                <div className='relative'>
                  <div className='absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none'>
                    <Search className='w-5 h-5 text-gray-400' />
                  </div>
                  <input
                    type='text'
                    value={filters.search}
                    onChange={(e) =>
                      handleFilterChange("search", e.target.value)
                    }
                    placeholder='Search logs...'
                    className='block w-full py-2 pl-10 pr-3 text-white placeholder-gray-400 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
                  />
                </div>
              </div>

              <div className='grid grid-cols-1 gap-4 md:grid-cols-3'>
                {/* Log Level */}
                <div>
                  <label className='block mb-2 text-sm font-medium text-gray-300'>
                    Log Level
                  </label>
                  <select
                    value={filters.level}
                    onChange={(e) =>
                      handleFilterChange("level", e.target.value)
                    }
                    className='block w-full px-3 py-2 text-white bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
                  >
                    <option value='all'>All Levels</option>
                    <option value='error'>Error</option>
                    <option value='warning'>Warning</option>
                    <option value='info'>Info</option>
                    <option value='debug'>Debug</option>
                  </select>
                </div>

                {/* Source */}
                <div>
                  <label className='block mb-2 text-sm font-medium text-gray-300'>
                    Source
                  </label>
                  <select
                    value={filters.source}
                    onChange={(e) =>
                      handleFilterChange("source", e.target.value)
                    }
                    className='block w-full px-3 py-2 text-white bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
                  >
                    <option value='all'>All Sources</option>
                    <option value='system'>System</option>
                    <option value='camera'>Camera</option>
                  </select>
                </div>

                {/* Camera */}
                <div>
                  <label className='block mb-2 text-sm font-medium text-gray-300'>
                    Camera
                  </label>
                  <select
                    value={filters.camera}
                    onChange={(e) =>
                      handleFilterChange("camera", e.target.value)
                    }
                    className='block w-full px-3 py-2 text-white bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
                  >
                    <option value='all'>All Cameras</option>
                    {cameras.map((camera) => (
                      <option key={camera.id} value={camera.id.toString()}>
                        {camera.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className='flex items-center justify-between pt-4'>
                <div className='text-sm text-gray-400'>
                  Showing {logs.length} of {logs.length} logs
                  {hasActiveFilters && (
                    <span className='ml-2 text-blue-400'>(filtered)</span>
                  )}
                </div>
                <div className='flex space-x-2'>
                  {hasActiveFilters && (
                    <button
                      onClick={clearFilters}
                      className='inline-flex items-center px-3 py-2 text-sm font-medium text-gray-300 bg-gray-700 border border-gray-600 rounded-md hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500'
                    >
                      <X className='w-4 h-4 mr-1' />
                      Clear Filters
                    </button>
                  )}
                  <button
                    onClick={() => {
                      fetchLogs()
                      fetchStats()
                    }}
                    className='inline-flex items-center px-3 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500'
                  >
                    <RotateCw className='w-4 h-4 mr-1' />
                    Refresh
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Logs */}
        <div className='overflow-hidden bg-gray-800 border border-gray-700 rounded-lg'>
          {loading ? (
            <div className='flex items-center justify-center py-12'>
              <RotateCw className='w-8 h-8 mr-3 text-gray-400 animate-spin' />
              <span className='text-gray-400'>Loading logs...</span>
            </div>
          ) : logs.length === 0 ? (
            <div className='flex flex-col items-center justify-center py-12'>
              <div className='flex items-center justify-center w-16 h-16 mb-4 bg-gray-700 rounded-full'>
                <svg
                  className='w-8 h-8 text-gray-400'
                  fill='none'
                  stroke='currentColor'
                  viewBox='0 0 24 24'
                >
                  <path
                    strokeLinecap='round'
                    strokeLinejoin='round'
                    strokeWidth={1.5}
                    d='M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z'
                  />
                </svg>
              </div>
              <h3 className='mb-2 text-lg font-medium text-white'>
                No logs found
              </h3>
              <p className='max-w-sm text-center text-gray-400'>
                No logs are available at the moment.
              </p>
              {hasActiveFilters && (
                <button
                  onClick={clearFilters}
                  className='inline-flex items-center px-4 py-2 mt-4 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700'
                >
                  Clear Filters
                </button>
              )}
            </div>
          ) : (
            <div className='overflow-x-auto'>
              <table className='min-w-full divide-y divide-gray-700'>
                <thead className='bg-gray-900'>
                  <tr>
                    <th className='px-6 py-3 text-xs font-medium tracking-wider text-left text-gray-300 uppercase'>
                      Time
                    </th>
                    <th className='px-6 py-3 text-xs font-medium tracking-wider text-left text-gray-300 uppercase'>
                      Level
                    </th>
                    <th className='px-6 py-3 text-xs font-medium tracking-wider text-left text-gray-300 uppercase'>
                      Source
                    </th>
                    <th className='px-6 py-3 text-xs font-medium tracking-wider text-left text-gray-300 uppercase'>
                      Message
                    </th>
                  </tr>
                </thead>
                <tbody className='bg-gray-800 divide-y divide-gray-700'>
                  {logs.map((log) => (
                    <tr key={log.id} className='hover:bg-gray-700'>
                      <td className='px-6 py-4 text-sm text-gray-300 whitespace-nowrap'>
                        {formatTimestamp(log.timestamp)}
                      </td>
                      <td className='px-6 py-4 whitespace-nowrap'>
                        <span
                          className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full border ${getLogLevelColor(
                            log.level
                          )}`}
                        >
                          {log.level.toUpperCase()}
                        </span>
                      </td>
                      <td className='px-6 py-4 text-sm text-gray-300 whitespace-nowrap'>
                        <div className='flex items-center'>
                          <span className='mr-2'>{getSourceIcon(log)}</span>
                          {getCameraDisplay(log)}
                        </div>
                      </td>
                      <td className='max-w-md px-6 py-4 text-sm text-gray-300'>
                        <div className='break-words'>{log.message}</div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
