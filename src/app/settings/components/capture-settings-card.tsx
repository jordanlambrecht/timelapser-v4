// src/app/settings/components/capture-settings-card.tsx
"use client"

import { useState } from "react"
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
import { NumberInput } from "@/components/ui/number-input"
import { ImageTypeSlider } from "@/components/ui/image-type-slider"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { ThumbnailRegenerationModal } from "@/components/thumbnail-regeneration-modal"
import SwitchLabeled from "@/components/ui/switch-labeled"
import { Clock, Image as ImageIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { useSettings } from "@/contexts/settings-context"

export function CaptureSettingsCard() {
  const {
    captureInterval,
    generateThumbnails,
    imageCaptureType,
    saving,
    updateSetting
  } = useSettings()
  // Local state for thumbnail modal and confirmation
  const [thumbnailModalOpen, setThumbnailModalOpen] = useState(false)
  const [thumbnailConfirmOpen, setThumbnailConfirmOpen] = useState(false)

  // Local state for image format dialogs
  const [imageConversionDialogOpen, setImageConversionDialogOpen] =
    useState(false)
  const [imageFormatChangeDialogOpen, setImageFormatChangeDialogOpen] =
    useState(false)
  const [pendingImageFormat, setPendingImageFormat] = useState<"PNG" | "JPG">(
    "JPG"
  )

  const formatInterval = (seconds: number) => {
    const sec = seconds
    if (sec < 60) return `${sec} seconds`
    if (sec < 3600) return `${Math.floor(sec / 60)} minutes`
    return `${Math.floor(sec / 3600)} hours`
  }

  const handleImageCaptureTypeChange = (newType: "PNG" | "JPG") => {
    setPendingImageFormat(newType)
    setImageFormatChangeDialogOpen(true)
  }

  const handleImageFormatConfirm = () => {
    setImageFormatChangeDialogOpen(false)
    updateSetting('image_capture_type', pendingImageFormat)
    setImageConversionDialogOpen(true)
  }

  const handleImageFormatCancel = () => {
    setImageFormatChangeDialogOpen(false)
    updateSetting('image_capture_type', pendingImageFormat) // Still change the format, just don't convert existing
  }

  return (
    <>
      <Card className='transition-all duration-300 glass hover:glow'>
        <CardHeader>
          <CardTitle className='flex items-center space-x-2'>
            <Clock className='w-5 h-5 text-primary' />
            <span>Capture Settings</span>
          </CardTitle>
          <CardDescription>
            Configure image capture intervals and thumbnail generation
          </CardDescription>
        </CardHeader>
        <CardContent className='space-y-6'>
          <div className='space-y-4'>
            <div className='space-y-3 grid grid-cols-1 md:grid-cols-2 gap-x-8'>
              <div>
                <NumberInput
                  id='interval'
                  label='Interval (seconds)'
                  value={captureInterval}
                  onChange={(value) => updateSetting('capture_interval', value)}
                  min={1}
                  max={86400}
                  step={1}
                  className='bg-background/50 border-borderColor/50 focus:border-primary/50'
                />
                <div className='flex flex-col space-x-4'>
                  <Badge
                    variant='outline'
                    className='px-2 py-2 whitespace-nowrap'
                  >
                    ({formatInterval(captureInterval)})
                  </Badge>
                </div>
                <p className='text-xs text-muted-foreground'>
                  Range: 1 second to 24 hours (86,400 seconds)
                </p>
              </div>

              {/* Quick Presets */}
              <div className='space-y-4'>
                <Label className='text-xs text-muted-foreground'>
                  Quick Presets:
                </Label>
                <div className='grid grid-cols-2 sm:grid-cols-3 md:grid-cols-2 gap-2'>
                  {[
                    { label: "30s", value: 30, desc: "High detail" },
                    { label: "1m", value: 60, desc: "Detailed" },
                    { label: "5m", value: 300, desc: "Standard" },
                    { label: "15m", value: 900, desc: "Moderate" },
                    { label: "1h", value: 3600, desc: "Long-term" },
                    { label: "2h", value: 7200, desc: "Longer-term" },
                  ].map((preset) => (
                    <Button
                      key={preset.value}
                      type='button'
                      variant='outline'
                      size='sm'
                      onClick={() => updateSetting('capture_interval', preset.value)}
                      className={cn(
                        "text-xs h-8 px-2 border-borderColor/50 hover:border-primary/50 transition-all duration-300 ease-in-out",
                        captureInterval === preset.value
                          ? "bg-primary border-primary/50 text-blue"
                          : "bg-background/30 text-muted-foreground hover:text-foreground"
                      )}
                      disabled={saving}
                      title={preset.desc}
                    >
                      {preset.label}
                    </Button>
                  ))}
                </div>
              </div>
            </div>

            {/* Thumbnail Generation Toggle */}
            <div className='space-y-3 my-8'>
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
                <SwitchLabeled
                  id='thumbnails'
                  falseLabel='disabled'
                  trueLabel='enabled'
                  checked={generateThumbnails}
                  onCheckedChange={(value) => updateSetting('generate_thumbnails', value)}
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
                      onClick={() => setThumbnailConfirmOpen(true)}
                      className='text-xs border-cyan-500/50 text-cyan-300 hover:bg-cyan-500/20 hover:text-white hover:border-cyan-400'
                    >
                      <ImageIcon className='w-3 h-3 mr-2' />
                      Regenerate All Now
                    </Button>
                    <p className='mt-2 text-xs text-gray-500'>
                      Generate thumbnails for existing images that don't have
                      them
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Image Capture Type Selection */}
            <div className='space-y-3 my-8'>
              <div className='space-y-1'>
                <Label className='text-sm font-medium flex items-center space-x-2'>
                  <ImageIcon className='w-4 h-4 text-blue-400' />
                  <span>Image Capture Type</span>
                  <Badge
                    variant='secondary'
                    className='ml-2 text-xs bg-yellow-500/20 text-yellow-300 border-yellow-500/30'
                  >
                    Not Implemented
                  </Badge>
                </Label>
                <p className='text-xs text-muted-foreground'>
                  Choose the format for captured images (settings are saved but
                  feature is not active yet)
                </p>
              </div>
              <ImageTypeSlider
                value={imageCaptureType}
                onValueChange={handleImageCaptureTypeChange}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Thumbnail Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={thumbnailConfirmOpen}
        onClose={() => setThumbnailConfirmOpen(false)}
        onConfirm={() => {
          setThumbnailConfirmOpen(false)
          setThumbnailModalOpen(true)
        }}
        title='Regenerate All Thumbnails'
        description='Are you sure? This might take a while to process all existing images and generate thumbnails.'
        confirmLabel='Yes, Start Regeneration'
        cancelLabel='Cancel'
        variant='warning'
        icon={<ImageIcon className='w-6 h-6' />}
      />

      {/* Thumbnail Regeneration Modal */}
      <ThumbnailRegenerationModal
        isOpen={thumbnailModalOpen}
        onClose={() => setThumbnailModalOpen(false)}
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

      {/* Image Conversion Progress Modal */}
      <ThumbnailRegenerationModal
        isOpen={imageConversionDialogOpen}
        onClose={() => setImageConversionDialogOpen(false)}
      />
    </>
  )
}
