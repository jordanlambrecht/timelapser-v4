// src/app/logs/page.tsx
"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import {
  Search,
  FunnelIcon,
  X,
  RotateCw,
  TriangleAlert,
  CircleAlert,
  Bug,
  Sigma,
  Trash2,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
} from "lucide-react"
import { useTimezoneSettings } from "@/contexts/settings-context"
import {
  formatDateInTimezone,
  parseTimestamp,
  getConfiguredTimezone,
} from "@/lib/time-utils"
import { Camera } from "@/types"

// Log page constants - aligned with backend constants
const DEFAULT_LOG_PAGE_SIZE = 100
const LOG_SEARCH_DEBOUNCE_MS = 500

interface Log {
  id: number
  level: string
  message: string
  camera_id: number | null
  camera_name: string | null
  timestamp: string
}

interface LogStats {
  errors: number
  warnings: number
  info: number
  debug: number
  total: number
}

interface LogPagination {
  page: number
  limit: number
  total_pages: number
  total_items: number
  has_next: boolean
  has_previous: boolean
}

export default function LogsPage() {
  const [logs, setLogs] = useState<Log[]>([])
  const [cameras, setCameras] = useState<Camera[]>([])

  // Get timezone from settings
  const { timezone } = useTimezoneSettings()
  const [stats, setStats] = useState<LogStats>({
    errors: 0,
    warnings: 0,
    info: 0,
    debug: 0,
    total: 0,
  })
  const [loading, setLoading] = useState(true)
  const [statsLoading, setStatsLoading] = useState(true)

  // Pagination state
  const [pagination, setPagination] = useState<LogPagination>({
    page: 1,
    limit: DEFAULT_LOG_PAGE_SIZE,
    total_pages: 1,
    total_items: 0,
    has_next: false,
    has_previous: false,
  })

  // Filter states
  const [filters, setFilters] = useState({
    search: "",
    level: "all",
    source: "all",
    camera: "all",
  })

  // Debounced search state
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const searchTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const [showFilters, setShowFilters] = useState(true)

  // ETag caching for logs and stats
  const [logsETag, setLogsETag] = useState<string | null>(null)
  const [statsETag, setStatsETag] = useState<string | null>(null)

  // Expanded exception messages state
  const [expandedExceptions, setExpandedExceptions] = useState<Set<number>>(new Set())

  // Fetch cameras for filter dropdown
  useEffect(() => {
    fetchCameras()
  }, [])

  // Fetch stats only on initial load (not when filters change)
  useEffect(() => {
    fetchStats()
  }, [])

  // Debounce search input
  useEffect(() => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current)
    }

    searchTimeoutRef.current = setTimeout(() => {
      setDebouncedSearch(filters.search)
    }, LOG_SEARCH_DEBOUNCE_MS) // Use constant instead of hardcoded value

    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current)
      }
    }
  }, [filters.search])

  // Fetch logs when filters change (including debounced search)
  useEffect(() => {
    setPagination((prev) => ({ ...prev, page: 1 })) // Reset to page 1 when filters change
    fetchLogs(1)
  }, [filters.level, filters.source, filters.camera, debouncedSearch])

  // Fetch logs when page changes
  useEffect(() => {
    if (pagination.page > 1) {
      fetchLogs(pagination.page)
    }
  }, [pagination.page])

  // Fetch logs when limit changes
  useEffect(() => {
    fetchLogs(1) // Always fetch page 1 when limit changes
  }, [pagination.limit])

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
    setStatsLoading(true)
    try {
      const headers: Record<string, string> = {}
      if (statsETag) {
        headers["If-None-Match"] = statsETag
      }

      const response = await fetch("/api/logs/stats", { headers })

      if (response.status === 304) {
        // Not modified, use cached data
        setStatsLoading(false)
        return
      }

      if (response.ok) {
        const newETag = response.headers.get("etag")
        if (newETag) {
          setStatsETag(newETag)
        }

        const data = await response.json()

        // Handle the correct API response structure
        if (data && data.success && data.data && data.data.summary) {
          const summary = data.data.summary
          setStats({
            errors: summary.error_count || 0,
            warnings: summary.warning_count || 0,
            info: summary.info_count || 0,
            debug: summary.debug_count || 0,
            total: summary.total_logs || 0,
          })
        } else {
          console.error("Unexpected stats response structure:", data)
          setStats({
            errors: 0,
            warnings: 0,
            info: 0,
            debug: 0,
            total: 0,
          })
        }
      }
    } catch (error) {
      console.error("Failed to fetch log stats:", error)
      setStats({
        errors: 0,
        warnings: 0,
        info: 0,
        debug: 0,
        total: 0,
      })
    } finally {
      setStatsLoading(false)
    }
  }

  const fetchLogs = async (page = 1) => {
    setLoading(true)
    try {
      const params = new URLSearchParams()

      // Add pagination
      params.set("page", page.toString())
      params.set("limit", pagination.limit.toString())

      // Add filters
      if (filters.level !== "all") params.set("level", filters.level)
      if (filters.source !== "all") params.set("source", filters.source)
      if (filters.camera !== "all") params.set("camera_id", filters.camera)
      if (debouncedSearch.trim()) params.set("search", debouncedSearch.trim())

      const headers: Record<string, string> = {}
      if (logsETag) {
        headers["If-None-Match"] = logsETag
      }

      const response = await fetch(`/api/logs?${params.toString()}`, {
        headers,
      })

      if (response.status === 304) {
        // Not modified, use cached data
        setLoading(false)
        return
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const newETag = response.headers.get("etag")
      if (newETag) {
        setLogsETag(newETag)
      }

      const data = await response.json()

      // Handle standardized API response structure
      if (data && data.success && data.data) {
        const logsData = data.data.logs || []
        const paginationData = data.data.pagination || {}

        setLogs(Array.isArray(logsData) ? logsData : [])
        setPagination((prev) => ({
          ...prev,
          page: paginationData.page || page,
          total_pages: paginationData.total_pages || 1,
          total_items: paginationData.total_items || 0,
          has_next: paginationData.has_next || false,
          has_previous: paginationData.has_previous || false,
        }))
      } else if (data && data.logs) {
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
    setFilters((prev) => {
      const newFilters = { ...prev, [key]: value }

      // Clear camera filter when source is set to system, api, worker, etc.
      // Only allow camera filter when source is 'all' or 'camera'
      if (key === "source" && value !== "all" && value !== "camera") {
        newFilters.camera = "all"
      }

      return newFilters
    })
  }

  const clearFilters = () => {
    setFilters({
      search: "",
      level: "all",
      source: "all",
      camera: "all",
    })
  }

  const handlePageChange = (newPage: number) => {
    setPagination((prev) => ({ ...prev, page: newPage }))
  }

  const handleLimitChange = (newLimit: number) => {
    setPagination((prev) => ({ ...prev, limit: newLimit, page: 1 })) // Reset to page 1 when changing limit
  }

  const clearAllLogs = async () => {
    if (
      !confirm(
        "Are you sure you want to delete ALL logs? This action cannot be undone."
      )
    ) {
      return
    }

    try {
      const response = await fetch("/api/logs/cleanup?days_to_keep=0", {
        method: "DELETE",
      })

      if (response.ok) {
        const data = await response.json()
        if (data.success) {
          // Refresh logs and stats after clearing
          await fetchLogs(1)
          await fetchStats()
          // Show success message
          console.log(
            `Successfully deleted ${data.data?.deleted_count || 0} logs`
          )
        } else {
          throw new Error(data.message || "Failed to clear logs")
        }
      } else {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
    } catch (error) {
      console.error("Failed to clear all logs:", error)
      alert("Failed to clear logs. Please try again.")
    }
  }

  const hasActiveFilters = Object.values(filters).some(
    (value) => value !== "all" && value !== ""
  )

  // Check if camera filter should be disabled
  const isCameraFilterDisabled = filters.source !== "all" && filters.source !== "camera"

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
    const parsedDate = parseTimestamp(timestamp, timezone)
    if (!parsedDate) return "Invalid date"

    return formatDateInTimezone(parsedDate, timezone, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
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

  const detectExceptionMessage = (message: string) => {
    // Common exception patterns
    const exceptionPatterns = [
      /exception=\{[^}]*[^}]*Error[^}]*\}/gi,
      /exception=.*Error.*$/gi,
      /Traceback \(most recent call last\):/gi,
      /\b[A-Z][a-zA-Z]*Error:/gi,
      /\bException:/gi,
      /\bFailed to.*:\s*.*$/gi
    ];
    
    return exceptionPatterns.some(pattern => pattern.test(message));
  }

  const formatExceptionMessage = (message: string, logId: number) => {
    const isException = detectExceptionMessage(message);
    const isExpanded = expandedExceptions.has(logId);
    
    if (!isException) {
      return <div className='break-words'>{message}</div>;
    }
    
    // For exception messages, show abbreviated version with expand/collapse
    const shortMessage = message.length > 100 ? message.substring(0, 100) + '...' : message;
    
    return (
      <div className='break-words'>
        {isExpanded ? (
          <div>
            <pre className='whitespace-pre-wrap text-xs bg-gray-700 p-2 rounded mt-2 text-red-300'>
              {message}
            </pre>
            <button
              onClick={() => {
                const newSet = new Set(expandedExceptions);
                newSet.delete(logId);
                setExpandedExceptions(newSet);
              }}
              className='mt-2 text-blue-400 hover:text-blue-300 flex items-center text-sm'
            >
              <ChevronUp className='w-4 h-4 mr-1' />
              Show less
            </button>
          </div>
        ) : (
          <div>
            <div className='text-red-300'>{shortMessage}</div>
            <button
              onClick={() => {
                const newSet = new Set(expandedExceptions);
                newSet.add(logId);
                setExpandedExceptions(newSet);
              }}
              className='mt-1 text-blue-400 hover:text-blue-300 flex items-center text-sm'
            >
              <ChevronDown className='w-4 h-4 mr-1' />
              Show full exception
            </button>
          </div>
        )}
      </div>
    );
  }

  const StatCard = ({
    icon,
    count,
    label,
    colorClass,
    isLoading,
  }: {
    icon: React.ReactNode
    count: number
    label: string
    colorClass: string
    isLoading: boolean
  }) => (
    <div className='p-6 bg-gray-800 border border-gray-700 rounded-lg'>
      <div className='flex items-center'>
        <div className='flex-shrink-0'>{icon}</div>
        <div className='ml-4'>
          {isLoading ? (
            <>
              <div className='w-8 h-8 bg-gray-700 rounded animate-pulse mb-1'></div>
              <div className='w-16 h-4 bg-gray-700 rounded animate-pulse'></div>
            </>
          ) : (
            <>
              <div className={`text-2xl font-bold ${colorClass.split(" ")[0]}`}>
                {count}
              </div>
              <div className='text-sm text-gray-400'>{label}</div>
            </>
          )}
        </div>
      </div>
    </div>
  )

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
          <StatCard
            icon={<CircleAlert className='w-8 h-8 text-red-400' />}
            count={stats.errors}
            label='Errors'
            colorClass='text-red-400'
            isLoading={statsLoading}
          />

          <StatCard
            icon={<TriangleAlert className='w-8 h-8 text-yellow-400' />}
            count={stats.warnings}
            label='Warnings'
            colorClass='text-yellow-400'
            isLoading={statsLoading}
          />

          <StatCard
            icon={<CircleAlert className='w-8 h-8 text-blue-400' />}
            count={stats.info}
            label='Info'
            colorClass='text-blue-400'
            isLoading={statsLoading}
          />

          <StatCard
            icon={<Bug className='w-8 h-8 text-gray-400' />}
            count={stats.debug}
            label='Debug'
            colorClass='text-gray-400'
            isLoading={statsLoading}
          />

          <StatCard
            icon={<Sigma className='w-8 h-8 text-cyan' />}
            count={stats.total}
            label='Total Logs'
            colorClass='text-white'
            isLoading={statsLoading}
          />
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

              <div className='grid grid-cols-1 gap-4 md:grid-cols-4'>
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
                    <option value='api'>API</option>
                    <option value='worker'>Worker</option>
                    <option value='pipeline'>Pipeline</option>
                    <option value='database'>Database</option>
                    <option value='scheduler'>Scheduler</option>
                    <option value='middleware'>Middleware</option>
                    <option value='health'>Health</option>
                    <option value='camera'>Camera-Specific</option>
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
                    disabled={isCameraFilterDisabled}
                    className={`block w-full px-3 py-2 text-white border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                      isCameraFilterDisabled
                        ? "bg-gray-700 text-gray-500 cursor-not-allowed opacity-50"
                        : "bg-gray-700 hover:bg-gray-600"
                    }`}
                  >
                    <option value='all'>All Cameras</option>
                    {cameras.map((camera) => (
                      <option key={camera.id} value={camera.id.toString()}>
                        {camera.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Items Per Page */}
                <div>
                  <label className='block mb-2 text-sm font-medium text-gray-300'>
                    Items Per Page
                  </label>
                  <select
                    value={pagination.limit}
                    onChange={(e) => handleLimitChange(Number(e.target.value))}
                    className='block w-full px-3 py-2 text-white bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'
                  >
                    <option value={25}>25</option>
                    <option value={50}>50</option>
                    <option value={100}>100</option>
                    <option value={200}>200</option>
                    <option value={500}>500</option>
                  </select>
                </div>
              </div>

              <div className='flex items-center justify-between pt-4'>
                <div className='text-sm text-gray-400'>
                  Showing {(pagination.page - 1) * pagination.limit + 1} to{" "}
                  {Math.min(
                    pagination.page * pagination.limit,
                    pagination.total_items
                  )}{" "}
                  of {pagination.total_items} logs
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
                    onClick={clearAllLogs}
                    className='inline-flex items-center px-3 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500'
                  >
                    <Trash2 className='w-4 h-4 mr-1' />
                    Clear All Logs
                  </button>
                  <button
                    onClick={() => {
                      fetchLogs(pagination.page)
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
            <>
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
                          {formatExceptionMessage(log.message, log.id)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {pagination.total_pages > 1 && (
                <div className='flex items-center justify-between px-6 py-3 bg-gray-900 border-t border-gray-700'>
                  <div className='text-sm text-gray-400'>
                    Page {pagination.page} of {pagination.total_pages}
                  </div>
                  <div className='flex items-center space-x-2'>
                    <button
                      onClick={() => handlePageChange(pagination.page - 1)}
                      disabled={!pagination.has_previous}
                      className={`inline-flex items-center px-3 py-2 text-sm font-medium border rounded-md ${
                        pagination.has_previous
                          ? "text-white bg-gray-700 border-gray-600 hover:bg-gray-600"
                          : "text-gray-500 bg-gray-800 border-gray-700 cursor-not-allowed"
                      }`}
                    >
                      <ChevronLeft className='w-4 h-4 mr-1' />
                      Previous
                    </button>
                    <button
                      onClick={() => handlePageChange(pagination.page + 1)}
                      disabled={!pagination.has_next}
                      className={`inline-flex items-center px-3 py-2 text-sm font-medium border rounded-md ${
                        pagination.has_next
                          ? "text-white bg-gray-700 border-gray-600 hover:bg-gray-600"
                          : "text-gray-500 bg-gray-800 border-gray-700 cursor-not-allowed"
                      }`}
                    >
                      Next
                      <ChevronRight className='w-4 h-4 ml-1' />
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
