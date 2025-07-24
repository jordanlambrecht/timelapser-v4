// src/types/video-automation.ts
export enum VideoAutomationMode {
  MANUAL = "manual",
  SCHEDULED = "scheduled",
  MILESTONE = "milestone",
  CONTINUOUS = "continuous",
}

export interface CameraAutomationSettings {
  video_automation_mode: VideoAutomationMode
  enabled: boolean
  schedule_config?: AutomationScheduleConfig
  milestone_config?: MilestoneConfig
  continuous_config?: ContinuousConfig
}

export interface AutomationScheduleConfig {
  frequency: "daily" | "weekly" | "monthly"
  time: string // HH:MM format
  days?: number[] // Days of week (0-6) for weekly, days of month for monthly
  duration_hours?: number
  max_video_length_minutes?: number
}

export interface MilestoneConfig {
  trigger_interval_hours: number
  min_images_required: number
  max_video_length_minutes: number
  auto_cleanup: boolean
}

export interface ContinuousConfig {
  chunk_duration_hours: number
  overlap_minutes: number
  max_concurrent_jobs: number
  storage_limit_gb?: number
}
