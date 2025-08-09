// src/components/camera-card-automation-badge.tsx
"use client"

import { VideoAutomationMode } from "@/types/video-automation"
import { VideoAutomationBadge } from "@/components/video-automation-badge"

interface CameraCardAutomationBadgeProps {
  camera: {
    id: number
    video_automation_mode?: VideoAutomationMode
    automation_schedule?: {
      type: "daily" | "weekly"
      time: string
      day?: string
    }
    milestone_config?: {
      enabled: boolean
      thresholds: number[]
    }
  }
  className?: string
}

export function CameraCardAutomationBadge({
  camera,
  className = "",
}: CameraCardAutomationBadgeProps) {
  // Only show if camera has automation mode set (defaults to manual if not set)
  const automationMode =
    camera.video_automation_mode || VideoAutomationMode.MANUAL

  return (
    <VideoAutomationBadge
      mode={automationMode}
      schedule={camera.automation_schedule}
      milestoneConfig={camera.milestone_config}
      className={className}
      showTooltip={true}
    />
  )
}
