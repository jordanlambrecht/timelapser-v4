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
import { ThumbnailRegenerationModal } from "@/components/thumbnail-regeneration-modal"
import { SuperSwitch } from "@/components/ui/switch"
import { Image as ImageIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { useSettings } from "@/contexts/settings-context"

export function CaptureSettingsCard() {
  const {
    generateThumbnails,
    imageCaptureType,
    saving,
    setGenerateThumbnails,
    setImageCaptureType,
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

  return (
    <>
      <Card className='transition-all duration-300 glass hover:glow'>
        <CardHeader>
          <CardTitle className='flex items-center space-x-2'>
            <ImageIcon className='w-5 h-5 text-primary' />
            <span>Image Settings</span>
          </CardTitle>
          <CardDescription>
            Configure thumbnail generation and image capture type
          </CardDescription>
        </CardHeader>
        <CardContent className='space-y-6'>
          <div className='space-y-4'>
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
        onClose={() => {
          setImageConversionDialogOpen(false)
          setUserIsChangingFormat(false)
        }}
      />
    </>
  )
}
