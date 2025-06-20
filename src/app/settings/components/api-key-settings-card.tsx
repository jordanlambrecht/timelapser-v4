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

interface ApiKeySettingsCardProps {
  openWeatherApiKey: string
  setOpenWeatherApiKey: (value: string) => void
  apiKeyModified: boolean
  setApiKeyModified: (value: boolean) => void
  originalApiKeyHash: string
}

export function ApiKeySettingsCard({
  openWeatherApiKey,
  setOpenWeatherApiKey,
  apiKeyModified,
  setApiKeyModified,
  originalApiKeyHash,
}: ApiKeySettingsCardProps) {
  // Handler for API key input changes
  const handleApiKeyChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setOpenWeatherApiKey(value)
    setApiKeyModified(true) // Mark as modified when user starts typing
  }

  // Handler for when user focuses on the API key field
  const handleApiKeyFocus = () => {
    if (!apiKeyModified && originalApiKeyHash) {
      // Clear the masked value when user focuses to type new key
      setOpenWeatherApiKey("")
      setApiKeyModified(true)
    }
  }

  // Get the display value for the API key input
  const getApiKeyDisplayValue = () => {
    if (apiKeyModified || !originalApiKeyHash) {
      return openWeatherApiKey // Show actual input when modified or no existing key
    }
    // For existing unmodified keys, show a readable placeholder instead of empty
    return (
      "••••••••••••••••••••••••••••••••••••••••••••••••••••••••••••" +
      originalApiKeyHash.slice(-4)
    )
  }

  // Get the placeholder for the API key input
  const getApiKeyPlaceholder = () => {
    if (originalApiKeyHash && !apiKeyModified) {
      return "Click to enter new API key"
    }
    return "Enter your OpenWeather API key"
  }

  return (
    <Card className='transition-all duration-300 glass hover:glow'>
      <CardHeader>
        <CardTitle className='flex items-center space-x-2'>
          <Cloud className='w-5 h-5 text-blue-400' />
          <span>External Services</span>
          <Badge
            variant='secondary'
            className='ml-2 text-xs bg-yellow-500/20 text-yellow-300 border-yellow-500/30'
          >
            Not Implemented
          </Badge>
        </CardTitle>
        <CardDescription>
          Configure external API integrations (settings are saved but features
          are not active yet)
        </CardDescription>
      </CardHeader>
      <CardContent className='space-y-4'>
        <div className='space-y-3'>
          <Label htmlFor='openweather-key' className='text-sm font-medium'>
            OpenWeather API Key
          </Label>
          <PasswordInput
            id='openweather-key'
            value={getApiKeyDisplayValue()}
            onChange={handleApiKeyChange}
            onFocus={handleApiKeyFocus}
            placeholder={getApiKeyPlaceholder()}
            className='bg-background/50 border-borderColor/50 focus:border-primary/50'
          />
          <p className='text-xs text-muted-foreground'>
            Used for weather overlay data on timelapses
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
