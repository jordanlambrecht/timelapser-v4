export interface LogForCamera {
  id: number
  timestamp: string
  level: string
  message: string
  camera_id?: number
}

export interface LogSource {
  source: string
  log_count: number
  last_log_at: string | null
  error_count: number
  warning_count: number
}

export interface LogSourcesResponse {
  success: boolean
  data: {
    sources: LogSource[]
    total_sources: number
  }
  message: string
}
