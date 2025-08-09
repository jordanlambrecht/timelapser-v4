// src/app/settings/components/capture-settings-card.tsx
"use client"

import React, { useState } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { ToggleGroup } from "@/components/ui/toggle-group"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { SuperSwitch } from "@/components/ui/switch"
import { Input } from "@/components/ui/input"
import { Slider } from "@/components/ui/slider"
import { Image as ImageIcon, Zap, Settings } from "lucide-react"
import { toast } from "@/lib/toast"
import { cn } from "@/lib/utils"
import { useSettings } from "@/contexts/settings-context"

export function ImageSettingsCard() {
  const {
    imageCaptureType,
    imageQuality,
    rtspTimeoutSeconds,
    saving,

    setImageCaptureType,
    setImageQuality,
    setRtspTimeoutSeconds,
  } = useSettings()
  // Local state for thumbnail regeneration
  const [thumbnailRegenerateConfirmOpen, setThumbnailRegenerateConfirmOpen] =
    useState(false)
  const [isRegenerating, setIsRegenerating] = useState(false)

  // Local state for image format dialogs
  const [imageConversionDialogOpen, setImageConversionDialogOpen] =
    useState(false)
  const [imageFormatChangeDialogOpen, setImageFormatChangeDialogOpen] =
    useState(false)
  const [pendingImageFormat, setPendingImageFormat] = useState<"PNG" | "JPG">(
    imageCaptureType
  )
  const [userIsChangingFormat, setUserIsChangingFormat] = useState(false)

  // Only sync pendingImageFormat when user is not actively changing it
  React.useEffect(() => {
    if (!userIsChangingFormat) {
      console.log(
        "🔄 Syncing pendingImageFormat to context value:",
        imageCaptureType
      )
      setPendingImageFormat(imageCaptureType)
    }
  }, [imageCaptureType, userIsChangingFormat])

  const handleImageCaptureTypeChange = (newType: "PNG" | "JPG") => {
    console.log("🎯 Image type toggle clicked:", imageCaptureType, "→", newType)
    setUserIsChangingFormat(true)
    setPendingImageFormat(newType)
    setImageFormatChangeDialogOpen(true)
  }

  const handleImageFormatConfirm = () => {
    console.log("🔄 Image format confirmed:", pendingImageFormat)
    setImageFormatChangeDialogOpen(false)
    setImageCaptureType(pendingImageFormat)
    setImageConversionDialogOpen(true)
    // Keep the flag true until the conversion dialog is also closed
  }

  const handleImageFormatCancel = () => {
    console.log(
      "✅ Image format changed for future captures only:",
      pendingImageFormat
    )
    setImageFormatChangeDialogOpen(false)
    setUserIsChangingFormat(false)
    // Apply the change but don't show conversion dialog (user chose "Only Future Captures")
    setImageCaptureType(pendingImageFormat)
  }

  const handleRegenerateAllThumbnails = async () => {
    setIsRegenerating(true)
    setThumbnailRegenerateConfirmOpen(false)

    toast.info("Starting thumbnail regeneration...", {
      description: "Processing will begin shortly",
      duration: 3000,
    })

    try {
      const response = await fetch("/api/thumbnails/regenerate-all", {
        method: "POST",
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || "Failed to start regeneration")
      }

      toast.success("Thumbnail regeneration started", {
        description: "Check the thumbnail job queue for progress updates",
        duration: 5000,
      })
    } catch (error) {
      console.error("Error starting thumbnail regeneration:", error)
      toast.error("Failed to start thumbnail regeneration", {
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        duration: 5000,
      })
    } finally {
      setIsRegenerating(false)
    }
  }

  return (
    <>
      <Card className='transition-all duration-300 glass hover:glow'>
        <CardHeader>
          <CardTitle className='flex items-center space-x-2'>
            <ImageIcon className='w-5 h-5 text-primary' />
            <span>Image Settings</span>
          </CardTitle>
          <CardDescription>
            Configure image quality, RTSP timeouts, and capture format
          </CardDescription>
        </CardHeader>
        <CardContent className='space-y-6'>
          <div className='space-y-4'>
            {/* Thumbnail Generation Toggle */}
            {/* <div className='space-y-3 my-8'>
              <div className='flex items-center justify-between'>
                <div className='space-y-1'>
                  <Label
                    htmlFor='thumbnails'
                    className='text-sm font-medium flex items-center space-x-2'
                  >
                    <ImageIcon className='w-4 h-4 text-purple-light' />
                    <h3>Generate Thumbnails</h3>
                  </Label>
                  <p className='text-xs text-muted-foreground'>
                    Create small preview images for faster dashboard loading
                  </p>
                </div>
                <SuperSwitch
                  variant='labeled'
                  id='thumbnails'
                  falseLabel='disabled'
                  trueLabel='enabled'
                  checked={generateThumbnails}
                  onCheckedChange={(value: boolean) =>
                    setGenerateThumbnails(value)
                  }
                />
              </div>
              <div className='p-3 rounded-lg bg-background/30 border border-borderColor/30'>
                <div className='flex items-center space-x-2 text-xs text-muted-foreground'>
                  <div
                    className={cn(
                      "w-2 h-2 rounded-full",
                      generateThumbnails ? "bg-green-500" : "bg-gray-500"
                    )}
                  />
                  <span>
                    {generateThumbnails
                      ? "Thumbnails will be generated for faster dashboard performance"
                      : "Only full-size images will be saved (slower dashboard loading)"}
                  </span>
                </div>
                {generateThumbnails && (
                  <div className='mt-2 text-xs text-purple-light/70'>
                    Creates: 200×150 thumbnails + 800×600 small images alongside
                    full captures
                  </div>
                )}
                {generateThumbnails && (
                  <div className='mt-3 pt-3 border-t border-borderColor/20'>
                    <Button
                      type='button'
                      variant='outline'
                      size='sm'
                      onClick={() => setThumbnailRegenerateConfirmOpen(true)}
                      disabled={isRegenerating}
                      className='text-xs border-cyan-500/50 text-cyan-300 hover:bg-cyan-500/20 hover:text-white hover:border-cyan-400'
                    >
                      <ImageIcon className='w-3 h-3 mr-2' />
                      {isRegenerating ? "Processing..." : "Regenerate All Now"}
                    </Button>
                    <p className='mt-2 text-xs text-gray-500'>
                      Generate thumbnails for existing images that don't have
                      them
                    </p>
                  </div>
                )}
              </div>
            </div> */}

            {/* Image Capture Type Selection */}
            <div className='space-y-3 my-8'>
              <div className='space-y-1'>
                <div className='flex items-center space-x-2'>
                  <ImageIcon className='w-4 h-4 text-blue-400' />
                  <span className='text-sm font-medium'>
                    Image Capture Type
                  </span>
                  <Badge
                    variant='secondary'
                    className='ml-2 text-xs bg-yellow-500/20 text-yellow-300 border-yellow-500/30'
                  >
                    Not Implemented
                  </Badge>
                </div>
                <p className='text-xs text-muted-foreground'>
                  Choose the format for captured images (settings are saved but
                  feature is not active yet)
                </p>
              </div>
              <ToggleGroup
                options={[
                  { label: "PNG", value: "PNG" },
                  { label: "JPG", value: "JPG" },
                ]}
                value={pendingImageFormat}
                onValueChange={(value) =>
                  handleImageCaptureTypeChange(value as "PNG" | "JPG")
                }
                label='Image Format'
                colorTheme='cyan'
                borderFaded={true}
                borderNone={true}
                size='lg'
              />
            </div>

            {/* Image Quality Setting */}
            <div className='space-y-3 my-8'>
              <div className='space-y-1'>
                <div className='flex items-center space-x-2'>
                  <Settings className='w-4 h-4 text-green-400' />
                  <span className='text-sm font-medium'>
                    Image Quality
                  </span>
                </div>
                <p className='text-xs text-muted-foreground'>
                  JPEG compression quality (1-100, higher = better quality, larger files)
                </p>
              </div>
              <div className='space-y-4'>
                <div className='px-3'>
                  <Slider
                    value={[imageQuality]}
                    onValueChange={([value]) => setImageQuality(value)}
                    min={1}
                    max={100}
                    step={1}
                    className='w-full'
                  />
                  <div className='flex justify-between text-xs text-muted-foreground mt-2'>
                    <span>Low (1)</span>
                    <span className='font-medium text-primary'>Current: {imageQuality}</span>
                    <span>High (100)</span>
                  </div>
                </div>
              </div>
            </div>

            {/* RTSP Timeout Setting */}
            <div className='space-y-3 my-8'>
              <div className='space-y-1'>
                <div className='flex items-center space-x-2'>
                  <Zap className='w-4 h-4 text-orange-400' />
                  <span className='text-sm font-medium'>
                    RTSP Connection Timeout
                  </span>
                </div>
                <p className='text-xs text-muted-foreground'>
                  Maximum time in seconds to wait for camera connections
                </p>
              </div>
              <div className='space-y-2'>
                <Input
                  type='number'
                  value={rtspTimeoutSeconds}
                  onChange={(e) => setRtspTimeoutSeconds(parseInt(e.target.value) || 10)}
                  min={1}
                  max={60}
                  className='w-full'
                />
                <p className='text-xs text-muted-foreground'>
                  Recommended: 5-15 seconds. Lower values = faster failure detection, higher = more reliable for slow cameras.
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Thumbnail Regeneration Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={thumbnailRegenerateConfirmOpen}
        onClose={() => setThumbnailRegenerateConfirmOpen(false)}
        onConfirm={handleRegenerateAllThumbnails}
        title='Regenerate All Thumbnails'
        description='Are you sure? This will process all existing images and generate thumbnails. This may take several minutes depending on the number of images.'
        confirmLabel='Yes, Start Regeneration'
        cancelLabel='Cancel'
        variant='warning'
        icon={<Zap className='w-6 h-6' />}
        isLoading={isRegenerating}
      />

      {/* Image Format Change Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={imageFormatChangeDialogOpen}
        onClose={handleImageFormatCancel}
        onConfirm={handleImageFormatConfirm}
        title='Change Image Capture Type'
        description='This change will only impact future image captures. Do you want to convert existing image captures now? This may take awhile.'
        confirmLabel='Yes, Convert Existing Images'
        cancelLabel='No, Only Future Captures'
        variant='warning'
        icon={<ImageIcon className='w-6 h-6' />}
      />

      {/* Image Conversion Progress - For future implementation */}
      {/* TODO: Implement image conversion progress tracking when this feature is added */}
    </>
  )
}
