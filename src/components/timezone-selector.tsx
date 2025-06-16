"use client"

import { useState, useEffect } from 'react'
import TimezoneSelect, { type ITimezone } from 'react-timezone-select'

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
  className = ""
}: TimezoneSelectorProps) {
  const [selectedTimezone, setSelectedTimezone] = useState<ITimezone>(
    value || Intl.DateTimeFormat().resolvedOptions().timeZone
  )
  const [detectedTimezone, setDetectedTimezone] = useState<string>('')

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
      setDetectedTimezone('America/Chicago')
      if (!value) {
        setSelectedTimezone('America/Chicago')
        onChange('America/Chicago')
      }
    }
  }, [value, onChange])

  // Update selected timezone when value prop changes
  useEffect(() => {
    if (value && value !== selectedTimezone) {
      setSelectedTimezone(value)
    }
  }, [value, selectedTimezone])

  const handleTimezoneChange = (timezone: ITimezone) => {
    setSelectedTimezone(timezone)
    // Extract the timezone string value
    const timezoneValue = typeof timezone === 'string' ? timezone : timezone.value
    onChange(timezoneValue)
  }

  const getCurrentTime = (timezone: string) => {
    try {
      return new Date().toLocaleString('en-US', {
        timeZone: timezone,
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
      })
    } catch {
      return 'Unknown'
    }
  }

  const getTimezoneValue = () => {
    return typeof selectedTimezone === 'string' ? selectedTimezone : selectedTimezone.value
  }

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <label htmlFor="timezone-select" className="block text-sm font-medium text-gray-700">
          Timezone
        </label>
        
        {/* React Timezone Select Component */}
        <div className={className}>
          <TimezoneSelect
            value={selectedTimezone}
            onChange={handleTimezoneChange}
            isDisabled={disabled}
            // Style the react-select to match our design
            styles={{
              control: (provided, state) => ({
                ...provided,
                minHeight: '42px',
                borderColor: state.isFocused ? '#3b82f6' : '#d1d5db',
                borderRadius: '6px',
                boxShadow: state.isFocused ? '0 0 0 2px rgba(59, 130, 246, 0.1)' : 'none',
                '&:hover': {
                  borderColor: '#3b82f6'
                },
                backgroundColor: disabled ? '#f3f4f6' : 'white',
                cursor: disabled ? 'not-allowed' : 'default'
              }),
              option: (provided, state) => ({
                ...provided,
                backgroundColor: state.isSelected 
                  ? '#3b82f6' 
                  : state.isFocused 
                  ? '#eff6ff' 
                  : 'white',
                color: state.isSelected ? 'white' : '#374151',
                cursor: 'pointer'
              }),
              singleValue: (provided) => ({
                ...provided,
                color: '#374151'
              }),
              placeholder: (provided) => ({
                ...provided,
                color: '#9ca3af'
              })
            }}
            // Use original label style with GMT offset
            labelStyle="original"
          />
        </div>
      </div>
      
      {detectedTimezone && (
        <div className="text-sm text-gray-600">
          <span className="inline-flex items-center">
            <svg className="w-4 h-4 mr-1 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
            Detected timezone: {detectedTimezone}
          </span>
          {detectedTimezone !== getTimezoneValue() && (
            <button
              type="button"
              onClick={() => handleTimezoneChange(detectedTimezone)}
              className="ml-2 text-blue-600 hover:text-blue-800 underline text-sm"
              disabled={disabled}
            >
              Use detected
            </button>
          )}
        </div>
      )}
      
      <div className="text-xs text-gray-500">
        Selected timezone: <span className="font-mono">{getTimezoneValue()}</span>
        <br />
        Current time: <span className="font-mono">{getCurrentTime(getTimezoneValue())}</span>
      </div>
    </div>
  )
}
