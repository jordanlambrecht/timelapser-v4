// TypeScript types for video automation system
// Import base types
import { Camera } from "./cameras"
import { Timelapse } from "./timelapses"

export enum VideoAutomationMode {
  MANUAL = "manual",
  PER_CAPTURE = "per_capture",
  SCHEDULED = "scheduled",
  MILESTONE = "milestone",
}

export interface AutomationScheduleConfig {
  type: "daily" | "weekly"
  time: string // HH:MM format
  day?: string // Day name for weekly schedules
  timezone?: string // Override timezone
}

export interface MilestoneConfig {
  enabled: boolean
  thresholds: number[] // Image count thresholds
  reset_on_complete?: boolean // Reset count after timelapse completion
}

export interface CameraAutomationSettings {
  video_automation_mode: VideoAutomationMode
  automation_schedule?: AutomationScheduleConfig
  milestone_config?: MilestoneConfig
}

export interface TimelapseAutomationSettings {
  video_automation_mode?: VideoAutomationMode
  automation_schedule?: AutomationScheduleConfig
  milestone_config?: MilestoneConfig
}

export interface VideoGenerationJob {
  id: number
  timelapse_id: number
  camera_id: number
  camera_name: string
  trigger_type: "manual" | "per_capture" | "scheduled" | "milestone"
  status: "pending" | "processing" | "completed" | "failed" | "cancelled"
  priority: "low" | "medium" | "high"
  created_at: string
  started_at?: string
  completed_at?: string
  error_message?: string
  video_id?: number
  settings?: Record<string, any>
}

export interface VideoQueueStatus {
  pending: number
  processing: number
  completed: number
  failed: number
}

export interface ManualTriggerRequest {
  camera_id?: number
  timelapse_id?: number
  priority?: "low" | "medium" | "high"
}

export interface AutomationStats {
  queue: {
    pending_jobs: number
    processing_jobs: number
    completed_jobs: number
    failed_jobs: number
    jobs_today: number
    jobs_week: number
  }
  automation_modes: Record<string, number>
  triggers_week: Record<string, number>
}

// Enhanced camera and timelapse types with automation
export interface CameraWithAutomation extends Camera {
  video_automation_mode: VideoAutomationMode
  automation_schedule?: AutomationScheduleConfig
  milestone_config?: MilestoneConfig
}

export interface TimelapseWithAutomation extends Timelapse {
  video_automation_mode?: VideoAutomationMode
  automation_schedule?: AutomationScheduleConfig
  milestone_config?: MilestoneConfig
}

// Video Automation Component Props
export interface VideoAutomationBadgeProps {
  mode: VideoAutomationMode
}

export interface VideoAutomationStatusProps {
  camera: CameraWithAutomation
  jobs: VideoGenerationJob[]
}

export interface VideoAutomationSettingsProps {
  cameraId?: number
  initialSettings?: CameraAutomationSettings
}

export interface VideoQueueMonitorProps {
  showHeader?: boolean
  maxJobs?: number
  className?: string
}

// Hook Interfaces
export interface VideoJobEventData {
  job_id: string
  camera_id: number
  camera_name: string
  status: string
  progress?: number
  error?: string
  output_path?: string
}
