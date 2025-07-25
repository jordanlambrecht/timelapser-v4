// src/components/lazy-timelapses-section.tsx
"use client"

import { useEffect, useState } from "react"
import { TimelapseSectionSkeleton, TimelapseSectionError } from "./ui/timelapse-skeleton"
import type { TimelapseWithDetails } from "@/types/api"

interface LazyTimelapsesSectionProps {
  timelapses: TimelapseWithDetails[]
  loading: boolean
  error: string | null
  onLoad: () => Promise<void>
  children: (timelapses: TimelapseWithDetails[]) => React.ReactNode
}

export function LazyTimelapsesSection({
  timelapses,
  loading,
  error,
  onLoad,
  children,
}: LazyTimelapsesSectionProps) {
  const [hasLoaded, setHasLoaded] = useState(false)

  useEffect(() => {
    if (!hasLoaded && !loading && !error) {
      setHasLoaded(true)
      onLoad()
    }
  }, [hasLoaded, loading, error, onLoad])

  // Show skeleton while loading
  if (loading) {
    return <TimelapseSectionSkeleton count={3} />
  }

  // Show error state with retry
  if (error) {
    return (
      <TimelapseSectionError 
        error={error} 
        onRetry={() => {
          setHasLoaded(false)
          onLoad()
        }} 
      />
    )
  }

  // Show actual content when loaded
  return <>{children(timelapses)}</>
}