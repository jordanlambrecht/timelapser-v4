// src/app/settings/components/timezone-settings-card.tsx
"use client"

import { useState } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { TimezoneSelector } from "@/components/timezone-selector-combobox"
import { useSettings } from "@/contexts/settings-context"
import { Globe } from "lucide-react"

export function TimezoneSettingsCard() {
  const { timezone, saving, updateSetting } = useSettings()
  
  // Debug timezone changes
  const handleTimezoneChange = (newTimezone: string) => {
    console.log(
      "🎯 Settings page: timezone changing from",
      timezone,
      "to",
      newTimezone
    )
    updateSetting('timezone', newTimezone)
  }

  return (
    <Card className='transition-all duration-300 glass hover:glow'>
      <CardHeader className='mb-2 pb-0'>
        <CardTitle className='flex items-center space-x-2'>
          <Globe className='w-5 h-5 text-pink' />
          <span className='text-white'>Timezone Configuration</span>
        </CardTitle>
        <CardDescription>
          Set the timezone for accurate time calculations and display
        </CardDescription>
      </CardHeader>
      <CardContent>
        <TimezoneSelector
          value={timezone}
          onChange={handleTimezoneChange}
          disabled={saving}
        />
      </CardContent>
    </Card>
  )
}
