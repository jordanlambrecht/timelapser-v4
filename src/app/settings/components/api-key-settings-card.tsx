// src/app/settings/components/api-key-settings-card.tsx
"use client"

import { useState } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { PasswordInput } from "@/components/ui/password-input"
import { Cloud } from "lucide-react"
import { useSettings } from "@/contexts/settings-context"

export function ApiKeySettingsCard() {
  // This card is now reserved for future external API integrations
  // OpenWeather API key has been moved to Weather Settings
  
  return (
    <Card className='transition-all duration-300 glass hover:glow'>
      <CardHeader>
        <CardTitle className='flex items-center space-x-2'>
          <Cloud className='w-5 h-5 text-blue-400' />
          <span>External Services</span>
        </CardTitle>
        <CardDescription>
          Additional API integrations will be available here in future updates
        </CardDescription>
      </CardHeader>
      <CardContent className='space-y-4'>
        <div className='p-6 rounded-lg bg-background/30 border border-borderColor/30 text-center'>
          <Cloud className='w-8 h-8 text-muted-foreground mx-auto mb-3' />
          <p className='text-sm text-muted-foreground mb-2'>No additional services configured</p>
          <p className='text-xs text-muted-foreground'>
            OpenWeather API key is now managed in Weather Integration settings
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
