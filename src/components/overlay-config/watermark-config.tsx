// src/components/overlay-config/watermark-config.tsx
"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { NumberInput } from "@/components/ui/number-input"
import { ThemedSlider } from "@/components/ui/themed-slider"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  Upload,
  Image as ImageIcon,
  X,
  RotateCw,
  Scale,
  Zap,
  Droplets,
  Eye,
  EyeOff,
  Check,
  AlertCircle,
  FileImage,
} from "lucide-react"
import { useFileUpload, type FileWithPreview } from "@/hooks/use-file-upload"
import { useOverlayAssets } from "@/hooks/use-overlay-assets"
import { cn } from "@/lib/utils"
import { toast } from "@/lib/toast"

interface WatermarkSettings {
  imageUrl?: string
  assetId?: number
  imageScale?: number
  rotation?: number
  blur?: number
  opacity?: number
  dropShadow?: boolean
  shadowOffsetX?: number
  shadowOffsetY?: number
  shadowBlur?: number
  shadowColor?: string
  shadowOpacity?: number
}

interface WatermarkConfigProps {
  settings: WatermarkSettings
  onChange: (settings: Partial<WatermarkSettings>) => void
  className?: string
}

export function WatermarkConfig({
  settings,
  onChange,
  className,
}: WatermarkConfigProps) {
  const [isUploading, setIsUploading] = useState(false)
  const [previewVisible, setPreviewVisible] = useState(true)

  const {
    uploadAsset,
    getAssetUrl,
    isLoading: assetLoading,
  } = useOverlayAssets()

  // File upload configuration
  const [fileState, fileActions] = useFileUpload({
    accept: "image/*",
    maxSize: 10 * 1024 * 1024, // 10MB
    multiple: false,
    onFilesAdded: async (files: FileWithPreview[]) => {
      if (files.length > 0) {
        await handleImageUpload(files[0])
      }
    },
  })

  const handleImageUpload = async (fileWithPreview: FileWithPreview) => {
    if (!(fileWithPreview.file instanceof File)) return

    setIsUploading(true)
    try {
      const asset = await uploadAsset(fileWithPreview.file)
      if (asset) {
        onChange({
          imageUrl: getAssetUrl(asset.id),
          assetId: asset.id,
        })
        fileActions.clearFiles()
        toast.success("🖼️ Watermark image uploaded successfully!")
      }
    } catch (error) {
      console.error("Failed to upload watermark:", error)
      toast.error("❌ Failed to upload watermark image")
    } finally {
      setIsUploading(false)
    }
  }

  const handleRemoveImage = () => {
    onChange({
      imageUrl: undefined,
      assetId: undefined,
    })
    fileActions.clearFiles()
  }

  const handleSettingChange = (key: keyof WatermarkSettings, value: any) => {
    onChange({ [key]: value })
  }

  // Get current preview image
  const currentPreview = fileState.files[0]?.preview || settings.imageUrl

  return (
    <div className={cn("space-y-4", className)}>
      {/* Header */}
      <div className='flex items-center justify-between'>
        <div className='flex items-center space-x-2'>
          <ImageIcon className='w-4 h-4 text-cyan' />
          <h3 className='text-sm font-medium text-white'>
            Watermark Configuration
          </h3>
        </div>
        {settings.imageUrl && (
          <Button
            size='sm'
            variant='ghost'
            onClick={() => setPreviewVisible(!previewVisible)}
            className='text-grey-light hover:text-white h-6 px-2'
          >
            {previewVisible ? (
              <>
                <EyeOff className='w-3 h-3 mr-1' />
                Hide
              </>
            ) : (
              <>
                <Eye className='w-3 h-3 mr-1' />
                Show
              </>
            )}
          </Button>
        )}
      </div>

      {/* Image Upload/Drop Zone */}
      {!settings.imageUrl && (
        <div className='space-y-3'>
          <div
            onClick={fileActions.openFileDialog}
            onDragEnter={fileActions.handleDragEnter}
            onDragLeave={fileActions.handleDragLeave}
            onDragOver={fileActions.handleDragOver}
            onDrop={fileActions.handleDrop}
            className={cn(
              "relative border-2 border-dashed rounded-lg p-6 transition-all duration-200 cursor-pointer group",
              fileState.isDragging
                ? "border-cyan bg-cyan/10 scale-105"
                : "border-purple-muted/50 hover:border-cyan/70 hover:bg-cyan/5",
              isUploading && "pointer-events-none opacity-50"
            )}
          >
            <input {...fileActions.getInputProps()} className='sr-only' />

            <div className='flex flex-col items-center space-y-3'>
              <div
                className={cn(
                  "p-3 rounded-full transition-colors",
                  fileState.isDragging
                    ? "bg-cyan/20 text-cyan"
                    : "bg-purple/20 text-purple group-hover:bg-cyan/20 group-hover:text-cyan"
                )}
              >
                {isUploading ? (
                  <RotateCw className='w-6 h-6 animate-spin' />
                ) : (
                  <Upload className='w-6 h-6' />
                )}
              </div>

              <div className='text-center space-y-1'>
                <p className='text-sm font-medium text-white'>
                  {isUploading
                    ? "Uploading watermark..."
                    : "Drop watermark image here"}
                </p>
                <p className='text-xs text-grey-light'>
                  or click to browse • PNG, JPG, GIF up to 10MB
                </p>
              </div>

              {fileState.isDragging && (
                <Badge className='bg-cyan/20 text-cyan border-cyan/30'>
                  Release to upload
                </Badge>
              )}
            </div>
          </div>

          {fileState.errors.length > 0 && (
            <Alert className='border-red-500/30 bg-red-500/10'>
              <AlertCircle className='w-4 h-4 text-red-400' />
              <AlertDescription className='text-red-400'>
                {fileState.errors.join(", ")}
              </AlertDescription>
            </Alert>
          )}
        </div>
      )}

      {/* Image Preview & Controls */}
      {settings.imageUrl && previewVisible && (
        <div className='space-y-4'>
          {/* Preview */}
          <div className='relative'>
            <div className='bg-purple/10 border border-purple-muted/30 rounded-lg p-4'>
              <div className='flex items-center justify-between mb-3'>
                <Label className='text-white text-xs'>Preview</Label>
                <div className='flex items-center space-x-2'>
                  <Badge
                    variant='outline'
                    className='text-xs text-grey-light border-purple-muted/30'
                  >
                    {settings.imageScale || 100}% scale
                  </Badge>
                  <Button
                    size='sm'
                    variant='ghost'
                    onClick={handleRemoveImage}
                    className='text-red-400 hover:text-red-300 hover:bg-red-500/10 h-6 w-6 p-0'
                  >
                    <X className='w-3 h-3' />
                  </Button>
                </div>
              </div>

              <div className='relative bg-black/20 rounded border border-purple-muted/20 p-4 min-h-32 flex items-center justify-center'>
                {currentPreview ? (
                  <img
                    src={currentPreview}
                    alt='Watermark preview'
                    className='max-w-full max-h-24 object-contain'
                    style={{
                      transform: `scale(${
                        (settings.imageScale || 100) / 100
                      }) rotate(${settings.rotation || 0}deg)`,
                      filter: `blur(${settings.blur || 0}px) opacity(${
                        settings.opacity || 100
                      }%)`,
                    }}
                  />
                ) : (
                  <div className='flex items-center space-x-2 text-grey-light'>
                    <FileImage className='w-5 h-5' />
                    <span className='text-sm'>Loading preview...</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Transform Controls */}
          <div className='grid grid-cols-2 gap-3'>
            <div className='space-y-1'>
              <ThemedSlider
                label='Scale'
                value={settings.imageScale || 100}
                onChange={(value) => handleSettingChange("imageScale", value)}
                min={10}
                max={200}
                step={5}
                unit='%'
                icon={<Scale className='w-3 h-3' />}
              />
            </div>

            <div className='space-y-1'>
              <ThemedSlider
                label='Rotation'
                value={settings.rotation || 0}
                onChange={(value) => handleSettingChange("rotation", value)}
                min={-180}
                max={180}
                step={15}
                unit='°'
                icon={<RotateCw className='w-3 h-3' />}
              />
            </div>
          </div>

          {/* Effect Controls */}
          <div className='grid grid-cols-2 gap-3'>
            <div className='space-y-1'>
              <ThemedSlider
                label='Blur'
                value={settings.blur || 0}
                onChange={(value) => handleSettingChange("blur", value)}
                min={0}
                max={10}
                step={0.5}
                unit='px'
                icon={<Zap className='w-3 h-3' />}
              />
            </div>

            <div className='space-y-1'>
              <ThemedSlider
                label='Opacity'
                value={settings.opacity || 100}
                onChange={(value) => handleSettingChange("opacity", value)}
                min={0}
                max={100}
                step={5}
                unit='%'
                icon={<Droplets className='w-3 h-3' />}
              />
            </div>
          </div>

          {/* Drop Shadow Controls */}
          <div className='space-y-3 p-3 bg-purple/5 rounded-lg border border-purple-muted/20'>
            <div className='flex items-center justify-between'>
              <Label className='text-white text-xs'>Drop Shadow</Label>
              <Button
                size='sm'
                variant='ghost'
                onClick={() =>
                  handleSettingChange("dropShadow", !settings.dropShadow)
                }
                className={cn(
                  "h-6 px-2 text-xs",
                  settings.dropShadow
                    ? "bg-cyan/20 text-cyan hover:bg-cyan/30"
                    : "text-grey-light hover:text-white"
                )}
              >
                {settings.dropShadow ? (
                  <>
                    <Check className='w-3 h-3 mr-1' />
                    Enabled
                  </>
                ) : (
                  "Enable"
                )}
              </Button>
            </div>

            {settings.dropShadow && (
              <div className='grid grid-cols-2 gap-3'>
                <div className='space-y-1'>
                  <Label className='text-white text-xs'>Offset X</Label>
                  <NumberInput
                    value={settings.shadowOffsetX || 3}
                    onChange={(value) =>
                      handleSettingChange("shadowOffsetX", value)
                    }
                    min={-20}
                    max={20}
                    className='bg-blue/20 border-purple-muted/50 focus:border-pink/50 h-7 text-xs'
                  />
                </div>

                <div className='space-y-1'>
                  <Label className='text-white text-xs'>Offset Y</Label>
                  <NumberInput
                    value={settings.shadowOffsetY || 3}
                    onChange={(value) =>
                      handleSettingChange("shadowOffsetY", value)
                    }
                    min={-20}
                    max={20}
                    className='bg-blue/20 border-purple-muted/50 focus:border-pink/50 h-7 text-xs'
                  />
                </div>

                <div className='space-y-1'>
                  <Label className='text-white text-xs'>Blur</Label>
                  <NumberInput
                    value={settings.shadowBlur || 2}
                    onChange={(value) =>
                      handleSettingChange("shadowBlur", value)
                    }
                    min={0}
                    max={20}
                    className='bg-blue/20 border-purple-muted/50 focus:border-pink/50 h-7 text-xs'
                  />
                </div>

                <div className='space-y-1'>
                  <Label className='text-white text-xs'>Opacity</Label>
                  <NumberInput
                    value={Math.round((settings.shadowOpacity || 0.5) * 100)}
                    onChange={(value) =>
                      handleSettingChange("shadowOpacity", value / 100)
                    }
                    min={0}
                    max={100}
                    className='bg-blue/20 border-purple-muted/50 focus:border-pink/50 h-7 text-xs'
                  />
                </div>

                <div className='space-y-1 col-span-2'>
                  <Label className='text-white text-xs'>Color</Label>
                  <div className='flex items-center space-x-2'>
                    <div
                      className='w-7 h-7 rounded border border-purple-muted/50 cursor-pointer'
                      style={{
                        backgroundColor: settings.shadowColor || "#000000",
                      }}
                      onClick={() => {
                        const input = document.createElement("input")
                        input.type = "color"
                        input.value = settings.shadowColor || "#000000"
                        input.onchange = (e) => {
                          handleSettingChange(
                            "shadowColor",
                            (e.target as HTMLInputElement).value
                          )
                        }
                        input.click()
                      }}
                    />
                    <div className='flex-1 text-xs text-grey-light font-mono'>
                      {settings.shadowColor || "#000000"}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Quick Actions */}
          <div className='flex items-center justify-between pt-2 border-t border-purple-muted/20'>
            <Button
              size='sm'
              variant='ghost'
              onClick={fileActions.openFileDialog}
              className='text-cyan hover:text-cyan hover:bg-cyan/10 h-7 px-3 text-xs'
            >
              <Upload className='w-3 h-3 mr-1' />
              Change Image
            </Button>

            <div className='flex items-center space-x-2 text-xs text-grey-light'>
              <span>Processing order:</span>
              <Badge variant='outline' className='text-xs'>
                Scale → Rotate → Blur → Shadow → Opacity
              </Badge>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
