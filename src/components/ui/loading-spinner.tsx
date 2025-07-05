// src/components/ui/loading-spinner.tsx
"use client"

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Loader2 } from "lucide-react"

import { cn } from "@/lib/utils"

const spinnerVariants = cva("animate-spin text-current", {
  variants: {
    size: {
      xs: "w-3 h-3",
      sm: "w-4 h-4",
      md: "w-6 h-6",
      lg: "w-8 h-8",
      xl: "w-12 h-12",
    },
    color: {
      default: "text-current",
      primary: "text-primary",
      cyan: "text-cyan",
      purple: "text-purple",
      white: "text-white",
      muted: "text-muted-foreground",
    },
  },
  defaultVariants: {
    size: "md",
    color: "default",
  },
})

const borderSpinnerVariants = cva("rounded-full border-2 animate-spin", {
  variants: {
    size: {
      xs: "w-3 h-3 border",
      sm: "w-4 h-4 border-2",
      md: "w-6 h-6 border-2",
      lg: "w-8 h-8 border-2",
      xl: "w-12 h-12 border-4",
    },
    color: {
      default: "border-current/20 border-t-current",
      primary: "border-primary/20 border-t-primary",
      cyan: "border-cyan/20 border-t-cyan",
      purple: "border-purple/20 border-t-purple",
      white: "border-white/20 border-t-white",
      muted: "border-muted-foreground/20 border-t-muted-foreground",
    },
  },
  defaultVariants: {
    size: "md",
    color: "default",
  },
})

export interface LoadingSpinnerProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "color">,
    VariantProps<typeof spinnerVariants> {
  /**
   * Whether to show the Loader2 icon or a custom border spinner
   */
  variant?: "icon" | "border"
}

/**
 * LoadingSpinner - Flexible spinner component for inline usage
 *
 * Use this for buttons, form elements, and small loading areas.
 * For full-page loading, use PageLoader instead.
 *
 * @example
 * ```tsx
 * // In buttons
 * <Button disabled={loading}>
 *   {loading && <LoadingSpinner size="sm" className="mr-2" />}
 *   Save Changes
 * </Button>
 *
 * // Standalone
 * <LoadingSpinner variant="border" size="lg" color="cyan" />
 * ```
 */
export function LoadingSpinner({
  className,
  size,
  color,
  variant = "icon",
  ...props
}: LoadingSpinnerProps) {
  if (variant === "border") {
    // Custom border spinner matching the style seen in the codebase
    return (
      <div
        className={cn(borderSpinnerVariants({ size, color }), className)}
        {...props}
      />
    )
  }

  // Default icon spinner using Loader2
  return <Loader2 className={cn(spinnerVariants({ size, color }), className)} />
}
