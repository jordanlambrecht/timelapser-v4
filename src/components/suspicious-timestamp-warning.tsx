"use client"

import { Info } from "lucide-react"
import { isSuspiciousTimestamp } from "@/lib/time-utils"

interface SuspiciousTimestampWarningProps {
  timestamp: string | null | undefined
  type: "last_capture" | "next_capture"
  className?: string
}

export function SuspiciousTimestampWarning({
  timestamp,
  type,
  className = "",
}: SuspiciousTimestampWarningProps) {
  if (!timestamp || !isSuspiciousTimestamp(timestamp, type)) {
    return null
  }

  const getMessage = () => {
    if (type === "last_capture") {
      return "This time appears to be in the future. Is the timezone set correctly in Settings?"
    }
    return "This capture time seems unusually far in the future. Check timezone settings."
  }

  return (
    <div className={`inline-flex items-center relative ${className}`}>
      <Info
        className='peer w-4 h-4 text-amber-500 hover:text-amber-600 cursor-help'
        strokeWidth={2}
      />

      {/* Tooltip */}
      <div className='absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 hidden peer-hover:block z-10'>
        <div className='bg-yellow/95 text-background-100 text-xs rounded-lg px-3 py-2 max-w-xs shadow-lg border border-amber-700/50'>
          <div className='flex items-start space-x-2'>
            <Info className='w-3 h-3 text-background-300 mt-0.5 flex-shrink-0 text-warn' />
            <div>
              <p className='font-medium text-warn'>Timezone Issue?</p>
              <p className='text-background/90 mt-1'>{getMessage()}</p>
              <p className='text-background/80 mt-2 text-xs'>
                → <span className='underline'>Settings</span> → Timezone
                Configuration
              </p>
            </div>
          </div>

          {/* Arrow pointing down */}
          <div className='absolute top-full left-1/2 transform -translate-x-1/2'>
            <div className='w-2 h-2 bg-yellow/95 border-r border-b border-warn transform rotate-45'></div>
          </div>
        </div>
      </div>
    </div>
  )
}

interface TimestampWithWarningProps {
  timestamp: string | null | undefined
  type: "last_capture" | "next_capture"
  className?: string
}

export function TimestampWithWarning({
  timestamp,
  type,
  className = "",
}: TimestampWithWarningProps) {
  return (
    <SuspiciousTimestampWarning
      timestamp={timestamp}
      type={type}
      className={className}
    />
  )
}
