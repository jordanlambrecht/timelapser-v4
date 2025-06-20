// src/app/settings/components/info-cards.tsx
"use client"

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Info, Camera, Monitor } from "lucide-react"

export function InfoCards() {
  return (
    <div className='grid grid-cols-1 md:grid-cols-2 gap-6'>
      {/* Capture Guidelines Card */}
      <Card className='transition-all duration-300 glass hover:glow'>
        <CardHeader>
          <CardTitle className='flex items-center space-x-2'>
            <Camera className='w-5 h-5 text-blue-400' />
            <span>Capture Guidelines</span>
          </CardTitle>
          <CardDescription>
            Best practices for optimal timelapse results
          </CardDescription>
        </CardHeader>
        <CardContent className='space-y-4'>
          <div className='space-y-3'>
            <div className='flex items-start space-x-3'>
              <div className='w-2 h-2 rounded-full bg-blue-400 mt-2 flex-shrink-0' />
              <div>
                <p className='text-sm font-medium'>Lighting Conditions</p>
                <p className='text-xs text-muted-foreground'>
                  Consistent lighting produces the best results. Consider using
                  artificial lighting for indoor captures.
                </p>
              </div>
            </div>

            <div className='flex items-start space-x-3'>
              <div className='w-2 h-2 rounded-full bg-green-400 mt-2 flex-shrink-0' />
              <div>
                <p className='text-sm font-medium'>Stable Camera Position</p>
                <p className='text-xs text-muted-foreground'>
                  Mount your camera securely to prevent movement between frames.
                  Even small movements can be jarring in the final video.
                </p>
              </div>
            </div>

            <div className='flex items-start space-x-3'>
              <div className='w-2 h-2 rounded-full bg-yellow-400 mt-2 flex-shrink-0' />
              <div>
                <p className='text-sm font-medium'>Interval Selection</p>
                <p className='text-xs text-muted-foreground'>
                  Fast changes: 30s-1min • Slow changes: 5-15min • Very slow:
                  1-2 hours
                </p>
              </div>
            </div>

            <div className='flex items-start space-x-3'>
              <div className='w-2 h-2 rounded-full bg-purple-400 mt-2 flex-shrink-0' />
              <div>
                <p className='text-sm font-medium'>Storage Space</p>
                <p className='text-xs text-muted-foreground'>
                  Monitor disk usage regularly. High-resolution captures at
                  short intervals can consume significant storage.
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* System Info Card */}
      <Card className='transition-all duration-300 glass hover:glow'>
        <CardHeader>
          <CardTitle className='flex items-center space-x-2'>
            <Monitor className='w-5 h-5 text-green-400' />
            <span>System Information</span>
          </CardTitle>
          <CardDescription>
            Current system status and capabilities
          </CardDescription>
        </CardHeader>
        <CardContent className='space-y-4'>
          <div className='space-y-3'>
            <div className='flex items-center justify-between'>
              <span className='text-sm font-medium'>Capture Service</span>
              <Badge
                variant='outline'
                className='text-green-400 border-green-400/50'
              >
                Running
              </Badge>
            </div>

            <div className='flex items-center justify-between'>
              <span className='text-sm font-medium'>Thumbnail Generation</span>
              <Badge
                variant='outline'
                className='text-blue-400 border-blue-400/50'
              >
                Available
              </Badge>
            </div>

            <div className='flex items-center justify-between'>
              <span className='text-sm font-medium'>Video Generation</span>
              <Badge
                variant='outline'
                className='text-purple-400 border-purple-400/50'
              >
                Available
              </Badge>
            </div>

            <div className='flex items-center justify-between'>
              <span className='text-sm font-medium'>Weather Integration</span>
              <Badge
                variant='outline'
                className='text-orange-400 border-orange-400/50'
              >
                Available
              </Badge>
            </div>

            <div className='flex items-center justify-between'>
              <span className='text-sm font-medium'>Real-time Updates</span>
              <Badge
                variant='outline'
                className='text-cyan-400 border-cyan-400/50'
              >
                Active
              </Badge>
            </div>

            <div className='pt-2 border-t border-borderColor/20'>
              <div className='flex items-center space-x-2'>
                <Info className='w-4 h-4 text-muted-foreground' />
                <p className='text-xs text-muted-foreground'>
                  All systems operational. Check the logs for detailed
                  information about capture activities.
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
