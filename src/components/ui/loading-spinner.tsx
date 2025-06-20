import React from "react"
import { Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"
import { cva, type VariantProps } from "class-variance-authority"

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

export interface LoadingSpinnerProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "color">,
    VariantProps<typeof spinnerVariants> {
  /**
   * Whether to show the Loader2 icon or a custom border spinner
   */
  variant?: "icon" | "border"
}

export function LoadingSpinner({
  className,
  size,
  color,
  variant = "icon",
  ...props
}: LoadingSpinnerProps) {
  if (variant === "border") {
    // Custom border spinner matching the style seen in the codebase
    const borderSpinnerVariants = cva("border-2 rounded-full animate-spin", {
      variants: {
        size: {
          xs: "w-3 h-3 border-[1px]",
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

    return (
      <div
        className={cn(borderSpinnerVariants({ size, color }), className)}
        {...props}
      />
    )
  }

  // Default icon spinner using Loader2
  return (
    <div className={className} {...props}>
      <Loader2 className={cn(spinnerVariants({ size, color }))} />
    </div>
  )
}
