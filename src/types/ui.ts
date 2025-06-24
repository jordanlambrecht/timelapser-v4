// UI component prop interfaces
// These are reusable prop interfaces for generic UI components

// Generic component props
export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {}

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {}

export interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg"
  className?: string
}

// Status and indicator components
export interface StatusIndicatorProps {
  status: "online" | "offline" | "unknown" | "active" | "inactive" | "error"
  variant?: "default" | "compact" | "detailed"
  size?: "sm" | "md" | "lg"
  showLabel?: boolean
  className?: string
  pulseOnline?: boolean
}

export interface CorruptionIndicatorProps {
  score: number
  degradedMode?: boolean
  size?: "sm" | "md" | "lg"
  showLabel?: boolean
  className?: string
}

export interface CorruptionAlertProps {
  camera: {
    id: number
    name: string
    degraded_mode_active?: boolean
    consecutive_corruption_failures?: number
    lifetime_glitch_count?: number
    recent_avg_score?: number
  }
  onReset?: (cameraId: number) => void
  className?: string
}

export interface CorruptionHealthSummaryProps {
  stats: {
    total_cameras: number
    cameras_healthy: number
    cameras_degraded: number
    system_health_score: number
  }
  className?: string
}

// Form and input components
export interface NumberInputProps {
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  placeholder?: string
  disabled?: boolean
  className?: string
}

export interface SwitchLabeledProps {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  trueLabel?: string
  falseLabel?: string
  disabled?: boolean
  className?: string
  id?: string
}

export interface TimezoneSelectorProps {
  value?: string
  onChange: (timezone: string) => void
  disabled?: boolean
  className?: string
}

// Media and display components
export interface VideoPlayerProps {
  src: string
  poster?: string
  title?: string
  className?: string
  showDownload?: boolean
  onDownload?: () => void
}

export interface ImageThumbnailProps {
  src: string
  alt: string
  width?: number
  height?: number
  className?: string
  fallback?: React.ReactNode
  onClick?: () => void
}

export interface ProgressBorderProps {
  progress: number // 0-100
  className?: string
  children: React.ReactNode
  color?: string
  strokeWidth?: number
}

// Layout and navigation components
export interface StatsCardProps {
  title: string
  value: string | number
  description?: string
  icon?: React.ComponentType<{ className?: string }>
  trend?: {
    value: number
    isPositive: boolean
  }
  className?: string
  color?: "pink" | "blue" | "green" | "orange" | "red"
}

export interface StatItemProps {
  label: string
  value: string | number
  icon?: React.ComponentType<{ className?: string }>
  trend?: {
    value: number
    isPositive: boolean
  }
  className?: string
}

export interface StatsGridProps {
  items: StatItemProps[]
  columns?: number
  className?: string
}

// Action and interaction components
export interface ActionItem {
  label: string
  onClick: () => void
  icon?: React.ComponentType<{ className?: string }>
  variant?: "default" | "destructive" | "outline" | "secondary"
  disabled?: boolean
}

export interface ActionButtonGroupProps {
  items: ActionItem[]
  orientation?: "horizontal" | "vertical"
  className?: string
}

// Specialized component interfaces
export interface ComboboxProps {
  options: Array<{
    value: string
    label: string
  }>
  value?: string
  onValueChange: (value: string) => void
  placeholder?: string
  searchPlaceholder?: string
  emptyText?: string
  disabled?: boolean
  className?: string
}

export interface ImageTypeSliderProps {
  value: "PNG" | "JPG"
  onValueChange: (value: "PNG" | "JPG") => void
  disabled?: boolean
  className?: string
}

export interface SpirographLogoProps {
  size?: number
  duration?: number
  className?: string
  animate?: boolean
}

export interface CameraImageWithFallbackProps {
  camera: any
  className?: string
  fallback?: React.ReactNode
  onClick?: () => void
}

export interface VideoQueueMonitorProps {
  showHeader?: boolean
  maxJobs?: number
  className?: string
}

export interface DashboardAutomationSummaryProps {
  className?: string
}

export interface CameraCardProps {
  camera: any
  timelapse?: any
  videos?: any[]
  onToggleTimelapse: (cameraId: number) => void
  onPauseTimelapse: (timelapseId: number) => void
  onResumeTimelapse: (timelapseId: number) => void
  onEditCamera: (camera: any) => void
  onDeleteCamera: (camera: any) => void
  onGenerateVideo: (camera: any) => void
}

export interface CameraCardAutomationBadgeProps {
  camera: any
  className?: string
}

export interface VideoAutomationBadgeProps {
  mode: any
  schedule?: any
  milestoneConfig?: any
  className?: string
  showTooltip?: boolean
}

export interface VideoAutomationStatusProps {
  status: string
  className?: string
}

export interface VideoAutomationSettingsProps {
  camera: any
  onSave: (settings: any) => void
  className?: string
}

// Dialog and modal components
export interface ConfirmationDialogProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  title: string
  description: string
  confirmText?: string
  cancelText?: string
  variant?: "default" | "destructive"
  loading?: boolean
}

// Additional Component Props
export interface SpirographLogoProps {
  className?: string
  size?: number
}

export interface SuspiciousTimestampWarningProps {
  timestamp: string | null | undefined
}

export interface TimestampWithWarningProps {
  timestamp: string | null | undefined
  className?: string
}

export interface DashboardAutomationSummaryProps {
  className?: string
}

// Data Interfaces
export interface RegenerationProgress {
  current: number
  total: number
  currentCamera?: string
  phase: "preparing" | "regenerating" | "cleanup" | "complete"
}

export interface Acknowledgement {
  category: string
  items: string[]
}

// Toast Interfaces
export interface ToastOptions {
  title?: string
  description?: string
  variant?: "default" | "destructive" | "success"
  duration?: number
}

export interface UndoToastOptions extends ToastOptions {
  onUndo: () => void
  undoText?: string
}
