// src/components/edit-timelapse-modal/crop-resize-tab.tsx
"use client"

import { useState, useEffect } from "react"
import Cropper from "react-easy-crop"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ToggleGroup } from "@/components/ui/toggle-group"
import { NumberInput } from "@/components/ui/number-input"
import { Switch } from "@/components/ui/switch"
import {
  Camera,
  ZoomIn,
  ZoomOut,
  DownloadCloud,
  RotateCw,
  FlipHorizontal,
  FlipVertical,
  Move,
  X,
  // Y,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "@/lib/toast"

interface CropResizeTabProps {
  timelapse: {
    id: number
    name: string
    status: string
    image_count: number
    start_date: string
    last_capture_at?: string
  }
  cameraId: number
  cameraName: string
  onDataChange?: () => void
}

export function CropResizeTab({
  timelapse,
  cameraId,
  cameraName,
  onDataChange,
}: CropResizeTabProps) {
  // Cropper state
  const [crop, setCrop] = useState({ x: 0, y: 0 })
  const [zoom, setZoom] = useState(1)
  const [rotation, setRotation] = useState(0)
  const [croppedAreaPixels, setCroppedAreaPixels] = useState<any>(null)
  const [imageUrl, setImageUrl] = useState<string>("")

  // Control states
  const [scaling, setScaling] = useState({
    width: 1920,
    height: 1080,
  })

  const [coordinates, setCoordinates] = useState({
    x: 0,
    y: 0,
  })

  const [aspectRatio, setAspectRatio] = useState("landscape")
  const [selectedRatio, setSelectedRatio] = useState("16x9")
  const [aspectValue, setAspectValue] = useState<number | undefined>(16 / 9)
  const [lockAspectRatio, setLockAspectRatio] = useState(true)

  const [flipSettings, setFlipSettings] = useState({
    horizontal: false,
    vertical: false,
  })

  const [zoomLevel, setZoomLevel] = useState(50)
  const [isGrabbingFrame, setIsGrabbingFrame] = useState(false)

  // Initialize image URL
  useEffect(() => {
    setImageUrl(`/api/cameras/${cameraId}/latest-image/small?t=${Date.now()}`)
  }, [cameraId])

  // Sync zoom level with zoom state (bidirectional)
  useEffect(() => {
    const newZoom = 1 + (zoomLevel - 50) / 50 // Convert 50-200% to 1-3 zoom
    if (Math.abs(zoom - newZoom) > 0.01) {
      // Prevent infinite loops
      setZoom(newZoom)
    }
  }, [zoomLevel])

  // Sync zoom back to slider when cropper changes zoom
  useEffect(() => {
    const newZoomLevel = Math.round((zoom - 1) * 50 + 50) // Convert 1-3 zoom to 50-200%
    if (Math.abs(zoomLevel - newZoomLevel) > 1) {
      // Prevent infinite loops
      setZoomLevel(newZoomLevel)
    }
  }, [zoom])

  // Handle crop completion
  const onCropComplete = (croppedArea: any, croppedAreaPixels: any) => {
    setCroppedAreaPixels(croppedAreaPixels)

    // Update scaling values to match crop dimensions
    setScaling({
      width: Math.round(croppedAreaPixels.width),
      height: Math.round(croppedAreaPixels.height),
    })

    // Update coordinates
    setCoordinates({
      x: Math.round(croppedAreaPixels.x),
      y: Math.round(croppedAreaPixels.y),
    })

    onDataChange?.()
  }

  const handleScalingChange = (field: "width" | "height", value: number) => {
    setScaling((prev) => ({ ...prev, [field]: value }))

    // Update crop area based on scaling input
    if (croppedAreaPixels) {
      const newCrop = { ...croppedAreaPixels }
      newCrop[field] = value

      // Maintain aspect ratio if one is set
      if (aspectValue && field === "width") {
        newCrop.height = Math.round(value / aspectValue)
      } else if (aspectValue && field === "height") {
        newCrop.width = Math.round(value * aspectValue)
      }

      setCroppedAreaPixels(newCrop)
    }

    onDataChange?.()
  }

  const handleAspectRatioChange = (type: string) => {
    setAspectRatio(type)
    onDataChange?.()
  }

  const handleRatioPresetChange = (ratio: string) => {
    setSelectedRatio(ratio)

    // Update aspect value for cropper
    let newAspectValue: number | undefined
    switch (ratio) {
      case "16x9":
        newAspectValue = 16 / 9
        break
      case "4x3":
        newAspectValue = 4 / 3
        break
      case "1x1":
        newAspectValue = 1
        break
      case "free":
        newAspectValue = undefined
        break
      default:
        newAspectValue = undefined
    }
    setAspectValue(newAspectValue)
    onDataChange?.()
  }

  const handleFlipChange = (direction: "horizontal" | "vertical") => {
    setFlipSettings((prev) => ({
      ...prev,
      [direction]: !prev[direction],
    }))
    onDataChange?.()
  }

  const handleGrabFreshFrame = async () => {
    setIsGrabbingFrame(true)
    try {
      // Trigger a manual capture to get fresh frame
      const response = await fetch(`/api/cameras/${cameraId}/capture-now`, {
        method: "POST",
      })

      if (!response.ok) {
        throw new Error("Failed to capture fresh frame")
      }

      // Wait a moment for the capture to process, then refresh image
      setTimeout(() => {
        setImageUrl(
          `/api/cameras/${cameraId}/latest-image/small?t=${Date.now()}`
        )
        toast.success("Fresh frame captured!")
      }, 2000)
    } catch (error) {
      console.error("Failed to grab fresh frame:", error)
      toast.error("Failed to capture fresh frame")
    } finally {
      setIsGrabbingFrame(false)
    }
  }

  return (
    <div className='grid grid-cols-1 lg:grid-cols-4 gap-6 h-full'>
      {/* Left Column - Preview */}
      <div className='lg:col-span-3 space-y-4'>
        <div className='flex items-center justify-between'>
          <div className='flex items-center gap-2'>
            <Camera className='w-5 h-5 text-cyan' />
            <h3 className='text-lg font-semibold text-white'>Preview</h3>
          </div>
          <div className='flex items-center gap-2'>
            <Button
              onClick={handleGrabFreshFrame}
              disabled={isGrabbingFrame}
              size='sm'
              className='bg-black/60 hover:bg-black/80 text-white border border-cyan/30'
            >
              {isGrabbingFrame ? (
                <>
                  <div className='w-4 h-4 mr-2 border-2 border-white border-t-transparent rounded-full animate-spin' />
                  Capturing...
                </>
              ) : (
                <>
                  <DownloadCloud className='w-4 h-4 mr-2' />
                  Grab Fresh Frame
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Interactive Image Cropper */}
        <div className='relative bg-black/20 border border-cyan/20 rounded-xl overflow-hidden aspect-video'>
          {imageUrl ? (
            <Cropper
              image={imageUrl}
              crop={crop}
              zoom={zoom}
              aspect={lockAspectRatio ? aspectValue : undefined}
              rotation={rotation}
              onCropChange={setCrop}
              onZoomChange={setZoom}
              onCropComplete={onCropComplete}
              style={{
                containerStyle: {
                  width: "100%",
                  height: "100%",
                  backgroundColor: "#1a1a1a",
                  borderRadius: "0.75rem",
                },
                mediaStyle: {
                  transform: `scaleX(${
                    flipSettings.horizontal ? -1 : 1
                  }) scaleY(${flipSettings.vertical ? -1 : 1})`,
                },
              }}
              showGrid={true}
              zoomSpeed={0.5}
              restrictPosition={true}
            />
          ) : (
            <div className='flex items-center justify-center w-full h-full text-gray-500'>
              <div className='text-center'>
                <Camera className='w-16 h-16 mx-auto text-gray-400 mb-4' />
                <p className='text-lg font-medium'>Loading preview...</p>
              </div>
            </div>
          )}
        </div>

        {/* Zoom Controls */}
        <div className='flex items-center gap-4 justify-center'>
          <Button
            variant='outline'
            size='sm'
            onClick={() => setZoomLevel(Math.max(10, zoomLevel - 10))}
            className='border-cyan/30 text-white hover:bg-cyan/20'
          >
            <ZoomOut className='w-4 h-4' />
          </Button>

          <div className='flex items-center gap-2'>
            <input
              type='range'
              min='10'
              max='200'
              value={zoomLevel}
              onChange={(e) => setZoomLevel(parseInt(e.target.value))}
              className='w-32 h-2 bg-cyan/20 rounded-lg appearance-none cursor-pointer slider'
            />
            <span className='text-sm text-white font-mono min-w-[3rem]'>
              {zoomLevel}%
            </span>
          </div>

          <Button
            variant='outline'
            size='sm'
            onClick={() => setZoomLevel(Math.min(200, zoomLevel + 10))}
            className='border-cyan/30 text-white hover:bg-cyan/20'
          >
            <ZoomIn className='w-4 h-4' />
          </Button>
        </div>
      </div>

      {/* Right Column - Controls */}
      <div className='space-y-6'>
        {/* Scaling & Position */}
        <div className='space-y-3'>
          <div className='flex items-center gap-2'>
            <Move className='w-4 h-4 text-cyan' />
            <Label className='text-white font-medium'>Scaling & Position</Label>
          </div>
          <div className='p-4 bg-cyan/5 border border-cyan/20 rounded-lg space-y-3'>
            <div className='grid grid-cols-2 gap-2'>
              <div className='space-y-2'>
                <Label className='text-cyan text-sm'>W</Label>
                <NumberInput
                  value={scaling.width}
                  onChange={(value) => handleScalingChange("width", value)}
                  min={100}
                  max={4096}
                  variant='buttons'
                  hideLabel={true}
                  className='bg-black/20 border-cyan/30 text-white'
                />
              </div>
              <div className='space-y-2'>
                <Label className='text-cyan text-sm'>H</Label>
                <NumberInput
                  value={scaling.height}
                  onChange={(value) => handleScalingChange("height", value)}
                  min={100}
                  max={4096}
                  variant='buttons'
                  hideLabel={true}
                  className='bg-black/20 border-cyan/30 text-white'
                />
              </div>
            </div>
            <div className='grid grid-cols-2 gap-2'>
              <div className='space-y-2'>
                <Label className='text-cyan text-sm flex items-center gap-1'>
                  <X className='w-3 h-3' />X
                </Label>
                <NumberInput
                  value={coordinates.x}
                  onChange={(value) =>
                    setCoordinates((prev) => ({ ...prev, x: value }))
                  }
                  min={0}
                  max={4096}
                  variant='buttons'
                  hideLabel={true}
                  className='bg-black/20 border-cyan/30 text-white'
                />
              </div>
              <div className='space-y-2'>
                {/* <Label className="text-cyan text-sm flex items-center gap-1">
                  <Y className="w-3 h-3" />Y
                </Label> */}
                <NumberInput
                  value={coordinates.y}
                  onChange={(value) =>
                    setCoordinates((prev) => ({ ...prev, y: value }))
                  }
                  min={0}
                  max={4096}
                  variant='buttons'
                  hideLabel={true}
                  className='bg-black/20 border-cyan/30 text-white'
                />
              </div>
            </div>
          </div>
        </div>

        {/* Aspect Ratio */}
        <div className='space-y-3'>
          <div className='flex items-center gap-2'>
            <RotateCw className='w-4 h-4 text-purple' />
            <Label className='text-white font-medium'>Aspect Ratio</Label>
          </div>
          <div className='p-4 bg-purple/5 border border-purple/20 rounded-lg space-y-4'>
            <div className='flex items-center justify-between'>
              <Label className='text-white text-sm'>Lock Aspect Ratio</Label>
              <Switch
                checked={lockAspectRatio}
                onCheckedChange={(checked) => {
                  setLockAspectRatio(checked)
                  if (!checked) {
                    setSelectedRatio("free")
                    setAspectValue(undefined)
                  } else {
                    setSelectedRatio("16x9")
                    setAspectValue(16 / 9)
                  }
                  onDataChange?.()
                }}
                colorTheme='cyan'
              />
            </div>

            {lockAspectRatio && (
              <>
                <ToggleGroup
                  options={[
                    { label: "Landscape", value: "landscape" },
                    { label: "Portrait", value: "portrait" },
                  ]}
                  value={aspectRatio}
                  onValueChange={handleAspectRatioChange}
                  label=''
                  colorTheme='cyan'
                  borderFaded={true}
                />

                <div className='space-y-2'>
                  {["16x9", "4x3", "1x1"].map((ratio) => (
                    <Button
                      key={ratio}
                      type='button'
                      variant='outline'
                      onClick={() => handleRatioPresetChange(ratio)}
                      className={cn(
                        "w-full justify-start text-left transition-all duration-300",
                        selectedRatio === ratio
                          ? "bg-purple/20 border-purple text-purple hover:bg-purple/30"
                          : "bg-black/20 border-purple-muted/30 text-grey-light hover:bg-purple/10 hover:border-purple hover:text-white"
                      )}
                    >
                      {ratio}
                    </Button>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Flip Image */}
        <div className='space-y-3'>
          <div className='flex items-center gap-2'>
            <FlipHorizontal className='w-4 h-4 text-green-400' />
            <Label className='text-white font-medium'>Flip Image</Label>
          </div>
          <div className='p-4 bg-green-500/5 border border-green-500/20 rounded-lg space-y-3'>
            <Button
              type='button'
              variant='outline'
              onClick={() => handleFlipChange("horizontal")}
              className={cn(
                "w-full justify-start text-left transition-all duration-300",
                flipSettings.horizontal
                  ? "bg-green-500/20 border-green-400 text-green-400 hover:bg-green-500/30"
                  : "bg-black/20 border-green-500/30 text-grey-light hover:bg-green-500/10 hover:border-green-500/50 hover:text-white"
              )}
            >
              <FlipHorizontal className='w-4 h-4 mr-2' />
              Flip Horizontal
            </Button>

            <Button
              type='button'
              variant='outline'
              onClick={() => handleFlipChange("vertical")}
              className={cn(
                "w-full justify-start text-left transition-all duration-300",
                flipSettings.vertical
                  ? "bg-green-500/20 border-green-400 text-green-400 hover:bg-green-500/30"
                  : "bg-black/20 border-green-500/30 text-grey-light hover:bg-green-500/10 hover:border-green-500/50 hover:text-white"
              )}
            >
              <FlipVertical className='w-4 h-4 mr-2' />
              Flip Vertical
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
