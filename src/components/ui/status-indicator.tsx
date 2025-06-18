// src/components/ui/status-indicator.tsx
import { cn } from "@/lib/utils"
import { cva, type VariantProps } from "class-variance-authority"
import {
  Circle,
  Pause,
  Square,
  Wifi,
  WifiOff,
  AlertTriangle,
} from "lucide-react"

/**
 * CVA configuration for the main status indicator badge
 * Defines variants for status, variant type, size, and glow effects
 */
const statusIndicatorVariants = cva(
  "inline-flex items-center rounded-full font-medium transition-all duration-200 border whitespace-nowrap",
  {
    variants: {
      /** Status-based color schemes */
      status: {
        // Timelapse states
        running: "bg-success/20 text-success border-success/40",
        paused: "bg-yellow/20 text-yellow border-yellow/40",
        completed: "bg-cyan/20 text-cyan border-cyan/40",
        stopped: "bg-purple-muted/20 text-purple-light border-purple-muted/40",
        archived: "bg-grey-light/20 text-grey-light border-grey-light/40",
        failed: "bg-failure/20 text-failure border-failure/40",
        generating: "bg-purple/20 text-purple-light border-purple/40",
        // Health states
        online: "bg-success/20 text-success border-success/40",
        offline: "bg-failure/20 text-failure border-failure/40",
        unknown: "bg-warn/20 text-warn border-warn/40",
        // Dynamic recording states
        recording:
          "bg-success/20 text-success border-success/40 shadow-sm shadow-success/20",
        snoozing:
          "bg-purple/20 text-purple-light border-purple/40 shadow-sm shadow-purple/20",
      },
      /** Visual variant styles */
      variant: {
        /** Default filled badge with background and border */
        default: "",
        /** Transparent background with hover effects */
        ghost: "bg-transparent border-transparent hover:bg-current/10",
        /** Blank slate for custom styling */
        custom: "",
      },
      /** Size variants affecting padding, gap, and text size */
      size: {
        xs: "gap-1 px-2 py-0.5 text-xs",
        sm: "gap-1.5 px-2.5 py-1 text-xs",
        md: "gap-2 px-3 py-1 text-xs",
        lg: "gap-2 px-3 py-1.5 text-sm",
        xl: "gap-2.5 px-4 py-2 text-sm",
      },
      /** Optional glow effects for active states */
      glow: {
        true: "",
        false: "",
      },
    },
    compoundVariants: [
      // Ghost variant overrides for different statuses
      {
        variant: "ghost",
        status: "running",
        class: "text-success hover:bg-success/10 border-transparent",
      },
      {
        variant: "ghost",
        status: "paused",
        class: "text-yellow hover:bg-yellow/10 border-transparent",
      },
      {
        variant: "ghost",
        status: "completed",
        class: "text-cyan hover:bg-cyan/10 border-transparent",
      },
      {
        variant: "ghost",
        status: "stopped",
        class: "text-purple-light hover:bg-purple-muted/10 border-transparent",
      },
      {
        variant: "ghost",
        status: "archived",
        class: "text-grey-light hover:bg-grey-light/10 border-transparent",
      },
      {
        variant: "ghost",
        status: "failed",
        class: "text-failure hover:bg-failure/10 border-transparent",
      },
      {
        variant: "ghost",
        status: "generating",
        class: "text-purple-light hover:bg-purple/10 border-transparent",
      },
      {
        variant: "ghost",
        status: "online",
        class: "text-success hover:bg-success/10 border-transparent",
      },
      {
        variant: "ghost",
        status: "offline",
        class: "text-failure hover:bg-failure/10 border-transparent",
      },
      {
        variant: "ghost",
        status: "unknown",
        class: "text-warn hover:bg-warn/10 border-transparent",
      },
      {
        variant: "ghost",
        status: "recording",
        class: "text-success hover:bg-success/10 border-transparent",
      },
      {
        variant: "ghost",
        status: "snoozing",
        class: "text-purple-light hover:bg-purple/10 border-transparent",
      },
      // Glow effects for active states
      {
        status: "recording",
        glow: true,
        class: "shadow-lg shadow-success/30",
      },
      {
        status: "running",
        glow: true,
        class: "shadow-lg shadow-success/30",
      },
      {
        status: "snoozing",
        glow: true,
        class: "shadow-lg shadow-purple/30",
      },
      {
        status: "generating",
        glow: true,
        class: "shadow-lg shadow-purple/30",
      },
      {
        status: "offline",
        glow: true,
        class: "shadow-lg shadow-failure/30",
      },
    ],
    defaultVariants: {
      status: "stopped",
      variant: "default",
      size: "md",
      glow: false,
    },
  }
)

/**
 * CVA configuration for status dots/icons
 * Handles sizing, colors, and pulse animations for dot indicators
 */
const statusDotVariants = cva("rounded-full", {
  variants: {
    status: {
      // Timelapse states
      running: "bg-success",
      paused: "bg-yellow",
      completed: "bg-cyan",
      stopped: "bg-purple-muted",
      archived: "bg-grey-light",
      failed: "bg-failure",
      generating: "bg-purple",
      // Health states
      online: "bg-success",
      offline: "bg-failure",
      unknown: "bg-warn",
      // Dynamic recording states
      recording: "bg-success",
      snoozing: "bg-purple",
    },
    size: {
      xs: "w-1.5 h-1.5",
      sm: "w-1.5 h-1.5",
      md: "w-2 h-2",
      lg: "w-2.5 h-2.5",
      xl: "w-3 h-3",
    },
    pulse: {
      true: "animate-pulse",
      false: "",
    },
  },
  compoundVariants: [
    {
      status: "running",
      pulse: true,
      class: "animate-pulse",
    },
    {
      status: "recording",
      pulse: true,
      class: "animate-pulse",
    },
    {
      status: "snoozing",
      pulse: true,
      class: "animate-pulse",
    },
    {
      status: "offline",
      pulse: true,
      class: "animate-pulse",
    },
    {
      status: "unknown",
      pulse: true,
      class: "animate-pulse",
    },
  ],
  defaultVariants: {
    status: "stopped",
    size: "md",
    pulse: false,
  },
})

/**
 * Props for the StatusIndicator component
 *
 * @interface StatusIndicatorProps
 * @extends {VariantProps<typeof statusIndicatorVariants>}
 */
interface StatusIndicatorProps
  extends VariantProps<typeof statusIndicatorVariants> {
  /** Additional CSS classes to apply to the component */
  className?: string
  /** Force pulse animation (auto-enabled for critical states) */
  showPulse?: boolean
  /** Whether to show the status icon/dot */
  showIcon?: boolean
  /** Type of icon to display: dot (colored circle) or lucide (semantic icon) */
  iconType?: "dot" | "lucide"
  /** Position of the icon relative to the badge */
  iconPosition?: "internal" | "external-left" | "external-right"
  /** Show only the dot without the badge wrapper */
  dotOnly?: boolean
  /**
   * Custom color overrides for the 'custom' variant
   * @example
   * ```tsx
   * customColors={{
   *   background: "#1e293b",
   *   text: "#f8fafc",
   *   border: "#475569",
   *   dot: "#10b981"
   * }}
   * ```
   */
  customColors?: {
    /** Background color for the badge */
    background?: string
    /** Text and icon color */
    text?: string
    /** Border color */
    border?: string
    /** Dot color (overrides text color for dots) */
    dot?: string
  }
}

/**
 * Labels for each status type
 * Maps status keys to display strings
 */
const statusLabels = {
  // Timelapse states
  running: "Running",
  paused: "Paused",
  completed: "Completed",
  stopped: "Stopped",
  archived: "Archived",
  failed: "Failed",
  generating: "Generating",
  // Health states
  online: "Online",
  offline: "Offline",
  unknown: "Unknown",
  // Dynamic recording states
  recording: "Recording",
  snoozing: "Snoozing",
} as const

/**
 * Lucide icon mapping for each status type
 * Used when iconType="lucide" to display semantic icons
 */
const statusIcons = {
  // Timelapse states
  running: Circle,
  paused: Pause,
  completed: Circle,
  stopped: Square,
  archived: Square,
  failed: AlertTriangle,
  generating: Circle,
  // Health states
  online: Wifi,
  offline: WifiOff,
  unknown: AlertTriangle,
  // Dynamic recording states
  recording: Circle,
  snoozing: Circle,
} as const

/**
 * StatusIndicator - A flexible, CVA-based status indicator component
 *
 * @description A comprehensive status indicator that supports multiple variants, sizes,
 * icon types, positioning options, and custom styling. Built with Class Variance Authority
 * for type-safe variant management.
 *
 * @features
 * - Multiple status types (timelapse, health, recording states)
 * - Three variants: default, ghost, custom
 * - Five size options: xs, sm, md, lg, xl
 * - Dual icon types: dot or Lucide icons
 * - Flexible positioning: internal, external-left, external-right
 * - Dot-only mode for minimal indicators
 * - Auto-pulse for critical states
 * - Glow effects for active states
 * - Full custom color support
 *
 * @example
 * ```tsx
 * // Basic usage
 * <StatusIndicator status="running" showIcon />
 *
 * // Ghost variant with external positioning
 * <StatusIndicator
 *   status="recording"
 *   variant="ghost"
 *   showIcon
 *   iconPosition="external-left"
 *   iconType="lucide"
 * />
 *
 * // Custom colors
 * <StatusIndicator
 *   status="online"
 *   variant="custom"
 *   customColors={{
 *     background: "#1e293b",
 *     text: "#f8fafc",
 *     border: "#475569",
 *     dot: "#10b981"
 *   }}
 * />
 *
 * // Dot only mode
 * <StatusIndicator status="failed" showIcon dotOnly />
 * ```
 */
export function StatusIndicator({
  status = "stopped",
  variant = "default",
  size = "md",
  glow = false,
  className,
  showPulse = false,
  showIcon = false,
  iconType = "dot",
  iconPosition = "internal",
  dotOnly = false,
  customColors,
}: StatusIndicatorProps) {
  const label = status ? statusLabels[status] || status : "Unknown"

  // Auto-enable pulse for certain statuses
  const shouldPulse =
    showPulse ||
    ["recording", "snoozing", "offline", "unknown"].includes(status || "")

  // Build custom styles for custom variant
  const customStyles =
    variant === "custom" && customColors
      ? {
          backgroundColor: customColors.background,
          color: customColors.text,
          borderColor: customColors.border,
        }
      : {}

  // Get the appropriate icon
  const getIcon = () => {
    if (!showIcon) return null

    if (iconType === "lucide" && status) {
      const LucideIcon = statusIcons[status]
      if (LucideIcon) {
        const iconSize =
          size === "xs" || size === "sm"
            ? "w-3 h-3"
            : size === "lg" || size === "xl"
            ? "w-4 h-4"
            : "w-3 h-3"
        const iconStyles =
          variant === "custom" && customColors?.text
            ? { color: customColors.text }
            : {}
        return (
          <LucideIcon
            className={cn(iconSize, shouldPulse && "animate-pulse")}
            style={iconStyles}
          />
        )
      }
    }

    // Default to dot
    const dotStyles =
      variant === "custom" && customColors?.dot
        ? {
            backgroundColor: customColors.dot,
          }
        : {}

    return (
      <span
        className={cn(
          statusDotVariants({
            status: variant === "custom" ? undefined : status,
            size,
            pulse: shouldPulse,
          }),
          variant === "custom" && "bg-current"
        )}
        style={dotStyles}
      />
    )
  }

  // For dot-only mode
  if (dotOnly) {
    return (
      <span className={cn("flex items-center", className)}>{getIcon()}</span>
    )
  }

  // For external positioning
  if (iconPosition === "external-left" && showIcon) {
    const gapSize =
      size === "xs"
        ? "gap-1"
        : size === "sm"
        ? "gap-1.5"
        : size === "md"
        ? "gap-2"
        : size === "lg"
        ? "gap-2"
        : "gap-2.5"
    return (
      <span className={cn("flex items-center", gapSize, className)}>
        {getIcon()}
        <span
          className={cn(
            statusIndicatorVariants({ status, variant, size, glow })
          )}
          style={customStyles}
        >
          {label}
        </span>
      </span>
    )
  }

  if (iconPosition === "external-right" && showIcon) {
    const gapSize =
      size === "xs"
        ? "gap-1"
        : size === "sm"
        ? "gap-1.5"
        : size === "md"
        ? "gap-2"
        : size === "lg"
        ? "gap-2"
        : "gap-2.5"
    return (
      <span className={cn("flex items-center", gapSize, className)}>
        <span
          className={cn(
            statusIndicatorVariants({ status, variant, size, glow })
          )}
          style={customStyles}
        >
          {label}
        </span>
        {getIcon()}
      </span>
    )
  }

  // Default internal positioning
  return (
    <span
      className={cn(
        statusIndicatorVariants({ status, variant, size, glow }),
        className
      )}
      style={customStyles}
    >
      {iconPosition === "internal" && getIcon()}
      {label}
    </span>
  )
}
