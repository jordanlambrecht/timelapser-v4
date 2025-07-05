// src/components/ui/page-loader.tsx
"use client"

import { cn } from "@/lib/utils"

export interface PageLoaderProps {
  /** Main loading message */
  title?: string
  /** Subtitle/description text */
  subtitle?: string
  /** Additional CSS classes */
  className?: string
  /** Size variant for the spinner */
  size?: "sm" | "md" | "lg"
}

/**
 * PageLoader - Standardized full-page loading component
 *
 * Provides consistent loading experience across the application with
 * customizable messaging while maintaining the signature dual-spinner design.
 *
 * @example
 * ```tsx
 * // Default loading
 * <PageLoader />
 *
 * // Custom messages
 * <PageLoader
 *   title="Loading camera details..."
 *   subtitle="Fetching images and timelapses"
 * />
 *
 * // Compact version
 * <PageLoader
 *   title="Processing..."
 *   size="sm"
 * />
 * ```
 */
export function PageLoader({
  title = "Loading dashboard...",
  subtitle = "Fetching camera data",
  className,
  size = "md",
}: PageLoaderProps) {
  const sizeClasses = {
    sm: {
      container: "min-h-[40vh]",
      spinner: "w-12 h-12",
      title: "text-sm",
      subtitle: "text-xs",
    },
    md: {
      container: "min-h-[60vh]",
      spinner: "w-16 h-16",
      title: "font-medium",
      subtitle: "text-sm",
    },
    lg: {
      container: "min-h-[80vh]",
      spinner: "w-20 h-20",
      title: "text-lg font-medium",
      subtitle: "text-base",
    },
  }

  const classes = sizeClasses[size]

  return (
    <div
      className={cn(
        "flex items-center justify-center",
        classes.container,
        className
      )}
    >
      <div className='space-y-6 text-center'>
        <div className='relative'>
          <div
            className={cn(
              "mx-auto border-4 rounded-full border-pink/20 border-t-pink animate-spin",
              classes.spinner
            )}
          />
          <div
            className={cn(
              "absolute inset-0 mx-auto border-4 rounded-full border-cyan/20 border-b-cyan animate-spin",
              classes.spinner
            )}
            style={{
              animationDirection: "reverse",
              animationDuration: "1.5s",
            }}
          />
        </div>
        <div>
          <p className={cn("text-white", classes.title)}>{title}</p>
          {subtitle && (
            <p className={cn("mt-1 text-grey-light/60", classes.subtitle)}>
              {subtitle}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
