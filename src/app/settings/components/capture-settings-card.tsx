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
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { ToggleGroup } from "@/components/ui/toggle-group"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { Image as ImageIcon } from "lucide-react"
import { useSettings } from "@/contexts/settings-context"

export function CaptureSettingsCard() {
  const { imageCaptureType, setImageCaptureType } = useSettings()

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
            <span>Image Capture Settings</span>
          </CardTitle>
          <CardDescription>
            Configure image capture format for your timelapses
          </CardDescription>
        </CardHeader>
        <CardContent className='space-y-6'>
          <div className='space-y-4'>
            {/* Image Capture Type Selection */}
            <div className='space-y-3'>
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
