// src/app/settings/components/image-format-dialogs.tsx
"use client"

import { useState } from "react"
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { ThumbnailRegenerationModal } from "@/components/thumbnail-regeneration-modal"
import { Image as ImageIcon } from "lucide-react"

interface ImageFormatDialogsProps {
  imageCaptureType: "PNG" | "JPG"
  onImageCaptureTypeChange: (newType: "PNG" | "JPG") => void
}

export function ImageFormatDialogs({
  imageCaptureType,
  onImageCaptureTypeChange,
}: ImageFormatDialogsProps) {
  const [imageConversionDialogOpen, setImageConversionDialogOpen] =
    useState(false)
  const [imageFormatChangeDialogOpen, setImageFormatChangeDialogOpen] =
    useState(false)
  const [pendingImageFormat, setPendingImageFormat] = useState<"PNG" | "JPG">(
    "JPG"
  )

  const handleImageCaptureTypeChange = (newType: "PNG" | "JPG") => {
    setPendingImageFormat(newType)
    setImageFormatChangeDialogOpen(true)
  }

  const handleImageFormatConfirm = () => {
    setImageFormatChangeDialogOpen(false)
    onImageCaptureTypeChange(pendingImageFormat)
    setImageConversionDialogOpen(true)
  }

  const handleImageFormatCancel = () => {
    setImageFormatChangeDialogOpen(false)
    onImageCaptureTypeChange(pendingImageFormat) // Still change the format, just don't convert existing
  }

  return (
    <>
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
