// src/components/edit-timelapse-modal/controls-tab.tsx
"use client"

import { Settings, Info } from "lucide-react"

interface ControlsTabProps {
  timelapse: {
    id: number
    name: string
    status: string
    image_count: number
    start_date: string
    last_capture_at?: string
  }
  cameraId: number
  cameraName: string
  onDataChange?: () => void
}

export function ControlsTab({
  timelapse,
  cameraId,
  cameraName,
  onDataChange,
}: ControlsTabProps) {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center space-y-4">
        <div className="w-16 h-16 mx-auto bg-purple/20 rounded-full flex items-center justify-center">
          <Settings className="w-8 h-8 text-purple" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-white mb-2">Controls</h3>
          <p className="text-grey-light/70 max-w-md">
            Advanced control settings for your timelapse recording and processing.
          </p>
        </div>
        <div className="flex items-center justify-center gap-2 text-sm text-cyan">
          <Info className="w-4 h-4" />
          <span>Coming soon - this will contain timelapse settings</span>
        </div>
      </div>
    </div>
  )
}