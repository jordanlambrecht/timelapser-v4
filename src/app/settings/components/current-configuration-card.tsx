// src/app/settings/components/current-configuration-card.tsx
"use client"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Settings, ImageIcon, Map, KeyIcon, Layers } from "lucide-react"

interface CurrentConfigurationCardProps {
  settings: {
    timezone: string
    openWeatherApiKey: string
    generateThumbnails: boolean
    imageCaptureType: "PNG" | "JPG"
    logLevel: string
  }
}

export function CurrentConfigurationCard({
  settings,
}: CurrentConfigurationCardProps) {

  return (
    <Card className='transition-all duration-300 glass hover:glow'>
      <CardHeader>
        <CardTitle className='flex items-center space-x-2'>
          <Settings className='w-5 h-5 text-green-500' />
          <span>Current Configuration</span>
        </CardTitle>
        <CardDescription>
          Your current timelapse system settings
        </CardDescription>
      </CardHeader>
      <CardContent className='space-y-4'>
        <div className='grid grid-cols-1 sm:grid-cols-2 gap-4'>
          <div className='flex items-center space-x-3 p-3 rounded-lg bg-background/30 border border-borderColor/30'>
            <Map className='w-4 h-4 text-orange-400' />
            <div>
              <p className='text-sm font-medium'>Timezone</p>
              <p className='text-xs text-muted-foreground'>
                {settings.timezone}
              </p>
            </div>
          </div>

          <div className='flex items-center space-x-3 p-3 rounded-lg bg-background/30 border border-borderColor/30'>
            <KeyIcon className='w-4 h-4 text-yellow-400' />
            <div>
              <p className='text-sm font-medium'>Weather API</p>
              <p className='text-xs text-muted-foreground'>
                {settings.openWeatherApiKey ? (
                  <Badge
                    variant='outline'
                    className='text-green-400 border-green-400/50'
                  >
                    Connected
                  </Badge>
                ) : (
                  <Badge
                    variant='outline'
                    className='text-red-400 border-red-400/50'
                  >
                    Not Connected
                  </Badge>
                )}
              </p>
            </div>
          </div>

          <div className='flex items-center space-x-3 p-3 rounded-lg bg-background/30 border border-borderColor/30'>
            <ImageIcon className='w-4 h-4 text-purple-400' />
            <div>
              <p className='text-sm font-medium'>Thumbnails</p>
              <p className='text-xs text-muted-foreground'>
                {settings.generateThumbnails ? (
                  <Badge
                    variant='outline'
                    className='text-green-400 border-green-400/50'
                  >
                    Enabled
                  </Badge>
                ) : (
                  <Badge
                    variant='outline'
                    className='text-gray-400 border-gray-400/50'
                  >
                    Disabled
                  </Badge>
                )}
              </p>
            </div>
          </div>

          <div className='flex items-center space-x-3 p-3 rounded-lg bg-background/30 border border-borderColor/30'>
            <ImageIcon className='w-4 h-4 text-cyan-400' />
            <div>
              <p className='text-sm font-medium'>Image Type</p>
              <p className='text-xs text-muted-foreground'>
                {settings.imageCaptureType}
                <Badge
                  variant='secondary'
                  className='ml-2 text-xs bg-yellow-500/20 text-yellow-300 border-yellow-500/30'
                >
                  Not Active
                </Badge>
              </p>
            </div>
          </div>

          <div className='flex items-center space-x-3 p-3 rounded-lg bg-background/30 border border-borderColor/30'>
            <Layers className='w-4 h-4 text-pink-400' />
            <div>
              <p className='text-sm font-medium'>Log Level</p>
              <p className='text-xs text-muted-foreground'>
                {settings.logLevel}
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
