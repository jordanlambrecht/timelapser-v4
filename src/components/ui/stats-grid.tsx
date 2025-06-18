// src/components/ui/stats-grid.tsx
"use client"

import { ReactNode } from "react"
import { cn } from "@/lib/utils"
import { LucideIcon } from "lucide-react"

interface StatItemProps {
  icon: LucideIcon
  label: string
  value: string | number
  subValue?: string
  accent?: "cyan" | "purple" | "yellow" | "success" | "failure"
  isActive?: boolean
  onClick?: () => void
  className?: string
}

interface StatsGridProps {
  children: ReactNode
  columns?: 2 | 3 | 4
  className?: string
}

export function StatItem({
  icon: Icon,
  label,
  value,
  subValue,
  accent = "purple",
  isActive = false,
  onClick,
  className,
}: StatItemProps) {
  const accentColors = {
    cyan: "text-cyan/70 group-hover:text-cyan",
    purple: "text-purple-light/70 group-hover:text-purple-light",
    yellow: "text-yellow/70 group-hover:text-yellow",
    success: "text-success/70 group-hover:text-success",
    failure: "text-failure/70 group-hover:text-failure",
  }

  const activeColors = {
    cyan: "border-cyan/50 bg-cyan/10 animate-pulse",
    purple: "border-purple/50 bg-purple/10 animate-pulse",
    yellow: "border-yellow/50 bg-yellow/10 animate-pulse",
    success: "border-success/50 bg-success/10 animate-pulse",
    failure: "border-failure/50 bg-failure/10 animate-pulse",
  }

  return (
    <div
      className={cn(
        "group p-3 border bg-black/20 rounded-xl border-purple-muted/20 transition-all duration-300",
        isActive && activeColors[accent],
        onClick && "cursor-pointer hover:bg-purple/10 hover:border-purple/30",
        className
      )}
      onClick={onClick}
    >
      <div className='flex items-center mb-1 space-x-2'>
        <Icon
          className={cn(
            "w-4 h-4 transition-colors",
            accentColors[accent],
            isActive && `text-${accent} animate-pulse`
          )}
        />
        <p className='text-xs font-medium text-grey-light/60'>{label}</p>
      </div>

      <div className='space-y-1'>
        <p className='font-bold text-white'>
          {typeof value === "number" ? value.toLocaleString() : value}
        </p>

        {subValue && (
          <p
            className={cn(
              "text-xs transition-colors",
              isActive ? `text-${accent}` : "text-grey-light/70"
            )}
          >
            {subValue}
          </p>
        )}
      </div>
    </div>
  )
}

export function StatsGrid({
  children,
  columns = 2,
  className,
}: StatsGridProps) {
  const gridCols = {
    2: "grid-cols-2",
    3: "grid-cols-3",
    4: "grid-cols-4",
  }

  return (
    <div className={cn("grid gap-4", gridCols[columns], className)}>
      {children}
    </div>
  )
}
