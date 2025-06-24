// Modal component prop interfaces
// These are prop interfaces for modal components

// Camera modals
export interface CameraModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: (camera: any) => void
  camera?: any
  title?: string
}

export interface EnhancedCameraModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: (camera: any) => void
  camera?: any
  title?: string
}

// Video modals
export interface VideoGenerationModalProps {
  isOpen: boolean
  onClose: () => void
  onGenerate: (settings: any) => void
  cameraId: number
  cameraName: string
  imageCount?: number
}

export interface VideoNameModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (name: string) => void
  cameraName: string
  defaultName?: string
}

export interface VideoProgressModalProps {
  isOpen: boolean
  cameraName: string
  videoName?: string
  imageCount?: number
}

// Timelapse modals (re-exported from timelapses.ts for convenience)
export type {
  TimelapseModalProps,
  TimelapseDetailsModalProps,
  TimelapseSettingsModalProps,
} from "./timelapses"

// Utility modals
export interface ThumbnailRegenerationModalProps {
  isOpen: boolean
  onClose: () => void
}

export interface SuspiciousTimestampWarningProps {
  timestamp: string
  type: "capture" | "creation" | "update"
  className?: string
}

export interface TimestampWithWarningProps {
  timestamp: string
  type: "capture" | "creation" | "update"
  format?: string
  className?: string
}

// Progress and status modals
export interface RegenerationProgress {
  active: boolean
  current?: number
  total?: number
  currentCamera?: string
  error?: string
}

// Data interfaces used in modals
export interface Acknowledgement {
  id: string
  title: string
  description: string
}

export interface CorruptionTestResult {
  corruption_score: number
  fast_score: number
  heavy_score: number | null
  processing_time_ms: number
  action_taken: string
}
