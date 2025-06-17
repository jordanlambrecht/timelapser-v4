// src/components/ui/progress-border.tsx
"use client"

import { cn } from "@/lib/utils"
import { useEffect, useState } from "react"

interface ProgressBorderProps {
  progress: number // 0-100
  className?: string
  children: React.ReactNode
  color?: string
  strokeWidth?: number
}

export function ProgressBorder({
  progress,
  className,
  children,
  color = "#06b6d4", // cyan
  strokeWidth = 2,
}: ProgressBorderProps) {
  const [animatedProgress, setAnimatedProgress] = useState(0)

  useEffect(() => {
    // Animate to the target progress
    const timer = setTimeout(() => {
      setAnimatedProgress(progress)
    }, 100)

    return () => clearTimeout(timer)
  }, [progress])

  // Calculate the stroke dash array for the progress
  // Use a rounded rectangle path for smooth animation
  const borderRadius = 12
  const strokeOffset = strokeWidth / 2
  
  // Create path for rounded rectangle border
  const pathData = `
    M ${borderRadius + strokeOffset} ${strokeOffset}
    L ${100 - borderRadius - strokeOffset} ${strokeOffset}
    Q ${100 - strokeOffset} ${strokeOffset} ${100 - strokeOffset} ${borderRadius + strokeOffset}
    L ${100 - strokeOffset} ${60 - borderRadius - strokeOffset}
    Q ${100 - strokeOffset} ${60 - strokeOffset} ${100 - borderRadius - strokeOffset} ${60 - strokeOffset}
    L ${borderRadius + strokeOffset} ${60 - strokeOffset}
    Q ${strokeOffset} ${60 - strokeOffset} ${strokeOffset} ${60 - borderRadius - strokeOffset}
    L ${strokeOffset} ${borderRadius + strokeOffset}
    Q ${strokeOffset} ${strokeOffset} ${borderRadius + strokeOffset} ${strokeOffset}
  `

  // Calculate approximate path length (rough estimate for rounded rectangle)
  const width = 100 - 2 * strokeOffset
  const height = 60 - 2 * strokeOffset
  const cornerRadius = borderRadius
  const straightSides = 2 * (width - 2 * cornerRadius) + 2 * (height - 2 * cornerRadius)
  const corners = 2 * Math.PI * cornerRadius
  const pathLength = straightSides + corners
  
  const progressLength = (animatedProgress / 100) * pathLength
  const dashArray = `${progressLength} ${pathLength - progressLength}`

  return (
    <div className={cn("relative", className)}>
      {/* Content */}
      <div className="relative z-10">
        {children}
      </div>
      
      {/* Progress overlay border */}
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none"
        viewBox="0 0 100 60"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Background border (very subtle) */}
        <path
          d={pathData}
          stroke="rgba(255, 255, 255, 0.08)"
          strokeWidth={strokeWidth}
          fill="none"
        />
        
        {/* Progress border */}
        <path
          d={pathData}
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          fill="none"
          strokeDasharray={dashArray}
          strokeDashoffset="0"
          className="transition-all duration-700 ease-in-out"
          style={{
            opacity: animatedProgress > 0 ? 0.7 : 0,
            filter: animatedProgress > 75 ? `drop-shadow(0 0 4px ${color}40)` : 'none'
          }}
        />
      </svg>
    </div>
  )
}
