export interface Video {
  id: number
  camera_id: number
  name: string
  settings?: {
    total_images?: number
    fps?: number
    [key: string]: any
  }
  file_path?: string
  status: "generating" | "completed" | "failed"
  image_count?: number
  file_size?: number
  duration_seconds?: number
  images_start_date?: string
  images_end_date?: string
  created_at: string
  updated_at: string
  calculated_fps?: number
  target_duration?: number
  actual_duration?: number
  fps_was_adjusted?: boolean
  adjustment_reason?: string
}
