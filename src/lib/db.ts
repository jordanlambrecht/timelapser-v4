// src/lib/db.ts
// ⚠️ DEPRECATED - DO NOT USE ⚠️
// This file provides direct database access from the frontend, which is a security risk.
// ALL database operations should go through the FastAPI backend for security.
// Use the proxy pattern with proxyToFastAPI() instead.

import { neon } from "@neondatabase/serverless"

if (!process.env.DATABASE_URL) {
  throw new Error(
    "DATABASE_URL must be set - but this should not be used in frontend!"
  )
}

// ⚠️ THIS SHOULD NOT BE USED - Use FastAPI proxy instead ⚠️
const sql = neon(process.env.DATABASE_URL)

export { sql }

// Type definitions for our database tables
export interface Camera {
  id: number
  name: string
  rtsp_url: string
  status: "active" | "inactive"
  time_window_start: string
  time_window_end: string
  use_time_window: boolean
  health_status: "online" | "offline" | "unknown"
  last_capture_at: string | null
  last_capture_success: boolean
  consecutive_failures: number
  created_at: string
  updated_at: string
}

// Camera with latest image data (from LATERAL join)
export interface CameraWithLatestImage extends Camera {
  timelapse_status?: "running" | "stopped" | "paused" | null
  timelapse_id?: number | null
  last_image_id?: number | null
  last_image_captured_at?: string | null
  last_image_file_path?: string | null
  last_image_file_size?: number | null
  last_image_day_number?: number | null
}

export interface Timelapse {
  id: number
  camera_id: number
  status: "running" | "stopped" | "paused"
  start_date: string | null
  image_count: number
  last_capture_at: string | null
  created_at: string
  updated_at: string
}

export interface Setting {
  id: number
  key: string
  value: string
  created_at: string
  updated_at: string
}

export interface Video {
  id: number
  camera_id: number
  name: string
  file_path: string
  status: "generating" | "completed" | "failed"
  settings: Record<string, any>
  image_count: number
  file_size: number | null
  duration_seconds: number | null
  images_start_date: string | null
  images_end_date: string | null
  created_at: string
  updated_at: string
}

export interface Image {
  id: number
  camera_id: number
  timelapse_id: number
  file_path: string
  captured_at: string
  day_number: number
  file_size: number | null
  created_at: string
}
