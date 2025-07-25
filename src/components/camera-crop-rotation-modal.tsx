// src/components/camera-crop-rotation-modal.tsx
"use client"

import { useState, useEffect, useRef } from "react"
import Cropper from "react-easy-crop"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Slider } from "@/components/ui/slider"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  RotateCw,
  Crop,
  Maximize2,
  Camera,
  Settings,
  Download,
  RefreshCw,
  Eye,
  EyeOff,
} from "lucide-react"
import { toast } from "@/lib/toast"
import type {
  CropRotationSettings,
  CropSettings,
  AspectRatioSettings,
} from "@/types/cameras"

interface CameraCropRotationModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: (settings: CropRotationSettings) => Promise<void>
  cameraId: number
  cameraName: string
  currentSettings?: CropRotationSettings
  testImageUrl?: string
}

export function CameraCropRotationModal({
  isOpen,
  onClose,
  onSave,
  cameraId,
  cameraName,
  currentSettings,
  testImageUrl,
}: CameraCropRotationModalProps) {
  // State for crop/rotation settings
  const [settings, setSettings] = useState<CropRotationSettings>({
    rotation: 0,
    crop: undefined,
    aspect_ratio: undefined,
    processing_order: ["crop", "rotate", "aspect_ratio"],
    preview_enabled: true,
  })

  // Cropper state
  const [crop, setCrop] = useState({ x: 0, y: 0 })
  const [zoom, setZoom] = useState(1)
  const [croppedAreaPixels, setCroppedAreaPixels] = useState<any>(null)
  const [testImage, setTestImage] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  // UI state
  const [activeTab, setActiveTab] = useState("crop")
  const [showPreview, setShowPreview] = useState(true)

  // Initialize settings
  useEffect(() => {
    if (isOpen) {
      setSettings(
        currentSettings || {
          rotation: 0,
          crop: undefined,
          aspect_ratio: undefined,
          processing_order: ["crop", "rotate", "aspect_ratio"],
          preview_enabled: true,
        }
      )

      // Load test image if provided
      if (testImageUrl) {
        setTestImage(testImageUrl)
      }
    }
  }, [isOpen, currentSettings, testImageUrl])

  // Handle crop complete
  const onCropComplete = (croppedArea: any, croppedAreaPixels: any) => {
    setCroppedAreaPixels(croppedAreaPixels)

    // Update crop settings
    const cropSettings: CropSettings = {
      x: croppedAreaPixels.x,
      y: croppedAreaPixels.y,
      width: croppedAreaPixels.width,
      height: croppedAreaPixels.height,
    }

    setSettings((prev) => ({
      ...prev,
      crop: cropSettings,
    }))
  }

  // Update rotation
  const updateRotation = (rotation: 0 | 90 | 180 | 270) => {
    setSettings((prev) => ({
      ...prev,
      rotation,
    }))
  }

  // Update aspect ratio settings
  const updateAspectRatio = (aspectRatio: Partial<AspectRatioSettings>) => {
    setSettings((prev) => ({
      ...prev,
      aspect_ratio: prev.aspect_ratio
        ? { ...prev.aspect_ratio, ...aspectRatio }
        : { enabled: false, mode: "crop", ...aspectRatio },
    }))
  }

  // Take test shot
  const takeTestShot = async () => {
    setLoading(true)
    try {
      const response = await fetch(`/api/cameras/${cameraId}/test-shot`, {
        method: "POST",
      })

      if (!response.ok) {
        throw new Error("Failed to capture test shot")
      }

      const data = await response.json()
      setTestImage(data.image_url)
      toast.success("Test shot captured successfully!")
    } catch (error) {
      console.error("Error taking test shot:", error)
      toast.error("Failed to capture test shot")
    } finally {
      setLoading(false)
    }
  }

  // Save settings
  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave(settings)
      toast.success("Crop/rotation settings saved!")
      onClose()
    } catch (error) {
      console.error("Error saving settings:", error)
      toast.error("Failed to save settings")
    } finally {
      setSaving(false)
    }
  }

  // Reset settings
  const resetSettings = () => {
    setSettings({
      rotation: 0,
      crop: undefined,
      aspect_ratio: undefined,
      processing_order: ["crop", "rotate", "aspect_ratio"],
      preview_enabled: true,
    })
    setCrop({ x: 0, y: 0 })
    setZoom(1)
    setCroppedAreaPixels(null)
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className='max-w-6xl h-[90vh] glass-strong border-purple-muted/50'>
        <DialogHeader>
          <DialogTitle className='flex items-center space-x-3 text-xl'>
            <div className='p-2 bg-gradient-to-br from-cyan/20 to-purple/20 rounded-xl'>
              <Crop className='w-6 h-6 text-white' />
            </div>
            <span className='text-white'>
              Crop & Rotation Settings - {cameraName}
            </span>
          </DialogTitle>
        </DialogHeader>

        <div className='flex flex-1 gap-6 min-h-0'>
          {/* Left Panel - Image Preview */}
          <div className='flex-1 min-w-0'>
            <Card className='h-full glass border-purple-muted/30'>
              <CardHeader className='pb-3'>
                <div className='flex items-center justify-between'>
                  <CardTitle className='text-white'>Preview</CardTitle>
                  <div className='flex items-center space-x-2'>
                    <Button
                      onClick={() => setShowPreview(!showPreview)}
                      variant='outline'
                      size='sm'
                      className='border-purple-muted/40'
                    >
                      {showPreview ? (
                        <EyeOff className='w-4 h-4' />
                      ) : (
                        <Eye className='w-4 h-4' />
                      )}
                      {showPreview ? "Hide" : "Show"} Preview
                    </Button>
                    <Button
                      onClick={takeTestShot}
                      variant='outline'
                      size='sm'
                      disabled={loading}
                      className='border-purple-muted/40'
                    >
                      {loading ? (
                        <RefreshCw className='w-4 h-4 animate-spin' />
                      ) : (
                        <Camera className='w-4 h-4' />
                      )}
                      Test Shot
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className='flex-1 p-0'>
                <div className='relative h-full bg-gray-900/50 rounded-lg overflow-hidden'>
                  {testImage && showPreview ? (
                    <div className='relative h-full'>
                      <Cropper
                        image={testImage}
                        crop={crop}
                        zoom={zoom}
                        rotation={settings.rotation}
                        aspect={
                          settings.aspect_ratio?.enabled &&
                          settings.aspect_ratio.ratio
                            ? (() => {
                                const [w, h] = settings.aspect_ratio.ratio
                                  .split(":")
                                  .map(Number)
                                return w / h
                              })()
                            : undefined
                        }
                        onCropChange={setCrop}
                        onZoomChange={setZoom}
                        onCropComplete={onCropComplete}
                        style={{
                          containerStyle: {
                            width: "100%",
                            height: "100%",
                            backgroundColor: "#1a1a1a",
                          },
                          mediaStyle: {
                            transform: `rotate(${settings.rotation}deg)`,
                          },
                        }}
                      />
                    </div>
                  ) : (
                    <div className='flex items-center justify-center h-full text-gray-400'>
                      <div className='text-center'>
                        <Camera className='w-16 h-16 mx-auto mb-4 opacity-50' />
                        <p className='text-lg'>No preview image</p>
                        <p className='text-sm'>
                          Take a test shot to see live preview
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Right Panel - Controls */}
          <div className='w-80 flex flex-col'>
            <Tabs
              value={activeTab}
              onValueChange={setActiveTab}
              className='flex-1'
            >
              <TabsList className='grid w-full grid-cols-3 bg-black/30 border border-purple-muted/30'>
                <TabsTrigger
                  value='crop'
                  className='data-[state=active]:bg-purple/20'
                >
                  <Crop className='w-4 h-4 mr-2' />
                  Crop
                </TabsTrigger>
                <TabsTrigger
                  value='rotation'
                  className='data-[state=active]:bg-purple/20'
                >
                  <RotateCw className='w-4 h-4 mr-2' />
                  Rotation
                </TabsTrigger>
                <TabsTrigger
                  value='aspect'
                  className='data-[state=active]:bg-purple/20'
                >
                  <Maximize2 className='w-4 h-4 mr-2' />
                  Aspect
                </TabsTrigger>
              </TabsList>

              <div className='mt-4 flex-1'>
                <TabsContent value='crop' className='space-y-4'>
                  <Card className='glass border-purple-muted/30'>
                    <CardHeader>
                      <CardTitle className='text-white'>
                        Crop Settings
                      </CardTitle>
                    </CardHeader>
                    <CardContent className='space-y-4'>
                      <div className='space-y-3'>
                        <Label className='text-white'>Zoom Level</Label>
                        <Slider
                          value={[zoom]}
                          onValueChange={(value) => setZoom(value[0])}
                          min={1}
                          max={3}
                          step={0.1}
                          className='w-full'
                        />
                        <div className='text-sm text-gray-400 text-center'>
                          {zoom.toFixed(1)}x
                        </div>
                      </div>

                      {settings.crop && (
                        <div className='p-3 bg-purple/10 border border-purple/20 rounded-lg'>
                          <div className='text-sm text-white space-y-1'>
                            <div>X: {settings.crop.x}px</div>
                            <div>Y: {settings.crop.y}px</div>
                            <div>Width: {settings.crop.width}px</div>
                            <div>Height: {settings.crop.height}px</div>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>

                <TabsContent value='rotation' className='space-y-4'>
                  <Card className='glass border-purple-muted/30'>
                    <CardHeader>
                      <CardTitle className='text-white'>
                        Rotation Settings
                      </CardTitle>
                    </CardHeader>
                    <CardContent className='space-y-4'>
                      <div className='grid grid-cols-2 gap-3'>
                        {[0, 90, 180, 270].map((rotation) => (
                          <Button
                            key={rotation}
                            onClick={() =>
                              updateRotation(rotation as 0 | 90 | 180 | 270)
                            }
                            variant={
                              settings.rotation === rotation
                                ? "default"
                                : "outline"
                            }
                            className={`h-12 ${
                              settings.rotation === rotation
                                ? "bg-purple text-white"
                                : "border-purple-muted/40 text-white hover:bg-purple/20"
                            }`}
                          >
                            {rotation}°
                          </Button>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </TabsContent>

                <TabsContent value='aspect' className='space-y-4'>
                  <Card className='glass border-purple-muted/30'>
                    <CardHeader>
                      <CardTitle className='text-white'>Aspect Ratio</CardTitle>
                    </CardHeader>
                    <CardContent className='space-y-4'>
                      <div className='flex items-center justify-between'>
                        <Label className='text-white'>
                          Enable Aspect Ratio
                        </Label>
                        <Switch
                          checked={settings.aspect_ratio?.enabled || false}
                          onCheckedChange={(enabled) =>
                            updateAspectRatio({ enabled })
                          }
                        />
                      </div>

                      {settings.aspect_ratio?.enabled && (
                        <>
                          <div className='space-y-2'>
                            <Label className='text-white'>Ratio</Label>
                            <Select
                              value={settings.aspect_ratio.ratio || "16:9"}
                              onValueChange={(ratio) =>
                                updateAspectRatio({ ratio })
                              }
                            >
                              <SelectTrigger className='bg-black/30 border-purple-muted/30 text-white'>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value='16:9'>
                                  16:9 (Widescreen)
                                </SelectItem>
                                <SelectItem value='4:3'>
                                  4:3 (Standard)
                                </SelectItem>
                                <SelectItem value='1:1'>
                                  1:1 (Square)
                                </SelectItem>
                                <SelectItem value='21:9'>
                                  21:9 (Ultrawide)
                                </SelectItem>
                                <SelectItem value='9:16'>
                                  9:16 (Portrait)
                                </SelectItem>
                              </SelectContent>
                            </Select>
                          </div>

                          <div className='space-y-2'>
                            <Label className='text-white'>Mode</Label>
                            <Select
                              value={settings.aspect_ratio.mode || "crop"}
                              onValueChange={(mode) =>
                                updateAspectRatio({
                                  mode: mode as "crop" | "letterbox",
                                })
                              }
                            >
                              <SelectTrigger className='bg-black/30 border-purple-muted/30 text-white'>
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value='crop'>
                                  Crop to fit
                                </SelectItem>
                                <SelectItem value='letterbox'>
                                  Letterbox (add padding)
                                </SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>
              </div>
            </Tabs>

            {/* Processing Order */}
            <Card className='mt-4 glass border-purple-muted/30'>
              <CardHeader>
                <CardTitle className='text-white text-sm'>
                  Processing Order
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className='flex items-center space-x-2 text-sm text-gray-400'>
                  {settings.processing_order.map((operation, index) => (
                    <div key={operation} className='flex items-center'>
                      <span className='capitalize'>{operation}</span>
                      {index < settings.processing_order.length - 1 && (
                        <span className='mx-2'>→</span>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        <DialogFooter className='gap-3 pt-4'>
          <Button
            onClick={resetSettings}
            variant='outline'
            className='border-purple-muted/40 text-white hover:bg-purple-muted/20'
          >
            Reset
          </Button>
          <Button
            onClick={onClose}
            variant='outline'
            className='border-purple-muted/40 text-white hover:bg-purple-muted/20'
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving}
            className='bg-gradient-to-r from-pink to-cyan hover:from-pink-dark hover:to-cyan text-black font-bold'
          >
            {saving ? (
              <>
                <RefreshCw className='w-4 h-4 mr-2 animate-spin' />
                Saving...
              </>
            ) : (
              <>
                <Download className='w-4 h-4 mr-2' />
                Save Settings
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
