"use client"

import { useState, useEffect } from "react"
import {
  useTimezoneSelect,
  allTimezones,
  type ITimezone,
} from "react-timezone-select"
import { Combobox } from "@/components/ui/combobox"
import { Info, Globe } from "lucide-react"
import { cn } from "@/lib/utils"

interface TimezoneSelectorProps {
  value?: string
  onChange: (timezone: string) => void
  disabled?: boolean
  className?: string
}

export function TimezoneSelector({
  value,
  onChange,
  disabled = false,
  className = "",
}: TimezoneSelectorProps) {
  const [selectedTimezone, setSelectedTimezone] = useState<string>(
    value || Intl.DateTimeFormat().resolvedOptions().timeZone
  )
  const [detectedTimezone, setDetectedTimezone] = useState<string>("")

  // Use the timezone select hook to get all options
  const { options, parseTimezone } = useTimezoneSelect({
    labelStyle: "original",
    timezones: allTimezones,
  })

  useEffect(() => {
    // Detect user's timezone
    try {
      const detected = Intl.DateTimeFormat().resolvedOptions().timeZone
      setDetectedTimezone(detected)

      // If no value provided, use detected timezone
      if (!value) {
        setSelectedTimezone(detected)
        onChange(detected)
      }
    } catch {
      // Fallback if Intl API not supported
      setDetectedTimezone("America/Chicago")
      if (!value) {
        setSelectedTimezone("America/Chicago")
        onChange("America/Chicago")
      }
    }
  }, [value, onChange])

  // Update selected timezone when value prop changes
  useEffect(() => {
    if (value && value !== selectedTimezone) {
      setSelectedTimezone(value)
    }
  }, [value, selectedTimezone])

  const handleTimezoneChange = (timezoneValue: string) => {
    console.log("🌍 Timezone changed to:", timezoneValue)

    if (!timezoneValue) {
      console.warn("⚠️ Empty timezone value received")
      return
    }

    setSelectedTimezone(timezoneValue)
    onChange(timezoneValue)
    console.log("✅ Timezone state updated and onChange called")
  }

  const handleUseDetected = () => {
    if (detectedTimezone) {
      handleTimezoneChange(detectedTimezone)
    }
  }

  const getCurrentTime = (timezone: string) => {
    try {
      return new Date().toLocaleString("en-US", {
        timeZone: timezone,
        hour: "2-digit",
        minute: "2-digit",
        hour12: true,
      })
    } catch {
      return "Unknown"
    }
  }

  // Convert react-timezone-select options to combobox format with enhanced search terms
  const comboboxOptions = options.map((option) => {
    // Extract searchable keywords from timezone identifier and label
    const timezoneParts = option.value.split("/") // e.g., ["America", "New_York"]
    const region = timezoneParts[0] || ""
    const city = timezoneParts[1]?.replace(/_/g, " ") || "" // "New_York" -> "New York"
    const subRegion = timezoneParts[2]?.replace(/_/g, " ") || ""

    // Extract additional keywords from the label
    const labelWords = option.label
      .replace(/[\(\)]/g, "") // Remove parentheses
      .split(/[\s,]+/) // Split on spaces and commas
      .filter((word) => word.length > 1) // Filter out single characters

    // Create comprehensive search keywords
    const keywords = [
      region,
      city,
      subRegion,
      ...labelWords,
      // Add common abbreviations and alternatives
      ...(city === "New York" ? ["NYC", "Eastern"] : []),
      ...(city === "Chicago" ? ["Central", "CST", "CDT"] : []),
      ...(city === "Los Angeles" ? ["Pacific", "PST", "PDT", "LA"] : []),
      ...(city === "Denver" ? ["Mountain", "MST", "MDT"] : []),
      ...(region === "America" ? ["US", "USA", "United States"] : []),
      ...(region === "Europe" ? ["EU", "European"] : []),
      ...(region === "Asia" ? ["Asian"] : []),
      ...(region === "Pacific" ? ["Oceania"] : []),
    ].filter(Boolean) // Remove empty strings

    return {
      value: option.value,
      label: option.label,
      keywords,
    }
  })

  return (
    <div className={`space-y-3 ${className}`}>
      {/* Current time preview */}
      <div className='  '>
        <div className='text-xs text-pink-dark space-y-1'>
          <div>
            <span className='text-sm font-bold pr-2'>Current time: </span>
            <span className='font-mono text-primary'>
              {getCurrentTime(selectedTimezone)} ({selectedTimezone})
            </span>
          </div>
        </div>
      </div>
      <div className='space-y-2'>
        <label
          htmlFor='timezone-select'
          className='block text-sm font-medium text-pink'
        >
          <div className='text-white flex items-center space-x-2'>
            <span>Select Timezone</span>
          </div>
        </label>

        {/* Custom Combobox with timezone options */}
        <Combobox
          selectableOptions={comboboxOptions}
          value={selectedTimezone}
          onValueChange={handleTimezoneChange}
          placeholder='Select timezone...'
          searchPlaceholder='Search by city, region, or timezone...'
          emptyMessage='No timezone found.'
          disabled={disabled}
          buttonWidth='w-full'
          contentClassName='max-h-[300px]'
          wrapperClassName={className}
        />
      </div>

      {/* Detected timezone info */}
      {detectedTimezone && (
        <div className='text-sm text-cyan'>
          <div
            className={cn(
              "flex items-center justify-between p-3 rounded-lg bg-cyan/10 border border-cyan",
              {
                ["bg-transparent p-0 border-0"]:
                  detectedTimezone == selectedTimezone,
              }
            )}
          >
            <span className='inline-flex items-center'>
              <Info className='w-4 h-4 mr-2 text-purple-light' />
              <span>
                <strong>Detected:</strong> {detectedTimezone}
              </span>
            </span>
            {detectedTimezone !== selectedTimezone && (
              <button
                type='button'
                onClick={handleUseDetected}
                className='px-3 py-1 text-xs font-medium text-purple-dark bg-pink-light rounded-full hover:bg-purple-light hover:text-blue transition-colors duration-200 ease-in-out'
                disabled={disabled}
              >
                Use detected
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
