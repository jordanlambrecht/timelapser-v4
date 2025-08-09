// src/components/overlay-preview-modal.tsx
"use client"

import { useState, useEffect } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Separator } from "@/components/ui/separator"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Eye,
  Camera,
  Loader2,
  AlertCircle,
  Image as ImageIcon,
  RefreshCw,
  Download,
  X,
} from "lucide-react"
import {
  useOverlayPreview,
  type OverlayPreviewRequest,
} from "@/hooks/use-overlay-preview"
import { useCameras } from "@/hooks/use-cameras"
import { useOverlaySSE } from "@/hooks/use-overlay-sse"

interface OverlayPreviewModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  overlayConfig: OverlayPreviewRequest["overlay_config"]
  presetName?: string
}

export function OverlayPreviewModal({
  open,
  onOpenChange,
  overlayConfig,
  presetName = "Preview",
}: OverlayPreviewModalProps) {
  const [selectedCameraId, setSelectedCameraId] = useState<number | null>(null)
  const { cameras, loading: camerasLoading } = useCameras()
  const { previewData, isGenerating, error, generatePreview, clearPreview } =
    useOverlayPreview()
  const { previewGenerationInProgress } = useOverlaySSE()

  // Auto-select first available camera
  useEffect(() => {
    if (cameras.length > 0 && !selectedCameraId) {
      setSelectedCameraId(cameras[0].id)
    }
  }, [cameras, selectedCameraId])

  // Clear preview when modal closes
  useEffect(() => {
    if (!open) {
      clearPreview()
    }
  }, [open, clearPreview])

  const handleGeneratePreview = async () => {
    if (!selectedCameraId) {
      return
    }

    await generatePreview({
      camera_id: selectedCameraId,
      overlay_config: overlayConfig,
    })
  }

  const handleDownloadPreview = () => {
    if (previewData?.image_path) {
      // Create download link for the preview image
      const link = document.createElement("a")
      link.href = `/data${previewData.image_path}`
      link.download = `overlay-preview-${presetName
        .toLowerCase()
        .replace(/\s+/g, "-")}.png`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    }
  }

  const selectedCamera = cameras.find((c) => c.id === selectedCameraId)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className='max-w-4xl max-h-[90vh] overflow-y-auto bg-black/95 backdrop-blur-xl border-purple/30'>
        <DialogHeader>
          <DialogTitle className='text-xl font-semibold flex items-center space-x-2'>
            <Eye className='w-5 h-5 text-purple' />
            <span className='gradient-text'>Overlay Preview: {presetName}</span>
          </DialogTitle>
        </DialogHeader>

        <div className='space-y-6 mt-4'>
          {/* Camera Selection */}
          <Card className='bg-gray-900/50 border-gray-700'>
            <CardContent className='p-4'>
              <div className='flex items-center justify-between'>
                <div className='space-y-1'>
                  <h3 className='text-sm font-medium flex items-center space-x-2'>
                    <Camera className='w-4 h-4 text-cyan' />
                    <span>Select Camera</span>
                  </h3>
                  <p className='text-xs text-muted-foreground'>
                    Choose which camera to use for the overlay preview
                  </p>
                </div>
                <div className='flex items-center space-x-3'>
                  <Select
                    value={selectedCameraId?.toString() || ""}
                    onValueChange={(value) =>
                      setSelectedCameraId(parseInt(value))
                    }
                    disabled={camerasLoading}
                  >
                    <SelectTrigger className='w-48'>
                      <SelectValue placeholder='Select camera...' />
                    </SelectTrigger>
                    <SelectContent>
                      {cameras.map((camera) => (
                        <SelectItem
                          key={camera.id}
                          value={camera.id.toString()}
                        >
                          <div className='flex items-center space-x-2'>
                            <Badge
                              variant={
                                camera.status === "online"
                                  ? "default"
                                  : "destructive"
                              }
                              className='w-2 h-2 p-0'
                            />
                            <span>{camera.name}</span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  <Button
                    onClick={handleGeneratePreview}
                    disabled={
                      selectedCameraId == null ||
                      isGenerating ||
                      (selectedCameraId != null &&
                        previewGenerationInProgress.has(selectedCameraId))
                    }
                    className='bg-gradient-to-r from-purple to-cyan hover:from-purple/90 hover:to-cyan/90'
                  >
                    {isGenerating ||
                    (selectedCameraId &&
                      previewGenerationInProgress.has(selectedCameraId)) ? (
                      <>
                        <Loader2 className='w-4 h-4 mr-2 animate-spin' />
                        Generating...
                      </>
                    ) : (
                      <>
                        <Eye className='w-4 h-4 mr-2' />
                        Generate Preview
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Error Display */}
          {error && (
            <Alert className='border-red-500/30 bg-red-500/10'>
              <AlertCircle className='w-4 h-4 text-red-500' />
              <AlertDescription className='text-sm text-red-500'>
                {error}
              </AlertDescription>
            </Alert>
          )}

          {/* Preview Display */}
          {previewData && (
            <div className='space-y-4'>
              <div className='flex items-center justify-between'>
                <h3 className='text-lg font-medium flex items-center space-x-2'>
                  <ImageIcon className='w-5 h-5 text-green-500' />
                  <span>Preview Result</span>
                </h3>
                <div className='flex items-center space-x-2'>
                  <Button
                    onClick={handleDownloadPreview}
                    variant='outline'
                    size='sm'
                    className='border-gray-600 hover:border-gray-500'
                  >
                    <Download className='w-4 h-4 mr-2' />
                    Download
                  </Button>
                  <Button
                    onClick={handleGeneratePreview}
                    variant='outline'
                    size='sm'
                    className='border-gray-600 hover:border-gray-500'
                    disabled={isGenerating}
                  >
                    <RefreshCw className='w-4 h-4 mr-2' />
                    Regenerate
                  </Button>
                </div>
              </div>

              <Separator />

              {/* Preview Images */}
              <div className='grid md:grid-cols-2 gap-4'>
                {/* Original Image */}
                <Card className='bg-gray-900/30 border-gray-700'>
                  <CardContent className='p-4'>
                    <h4 className='text-sm font-medium mb-3 text-gray-300'>
                      Original Image
                    </h4>
                    <div className='relative bg-gray-800 rounded-lg overflow-hidden'>
                      <img
                        src={`/data${previewData.test_image_path}`}
                        alt='Original camera image'
                        className='w-full h-auto'
                        onError={(e) => {
                          e.currentTarget.src = "/assets/placeholder-camera.jpg"
                        }}
                      />
                    </div>
                    <p className='text-xs text-muted-foreground mt-2'>
                      Source: {selectedCamera?.name || "Unknown Camera"}
                    </p>
                  </CardContent>
                </Card>

                {/* Preview with Overlay */}
                <Card className='bg-gray-900/30 border-gray-700'>
                  <CardContent className='p-4'>
                    <h4 className='text-sm font-medium mb-3 text-green-400'>
                      With Overlay
                    </h4>
                    <div className='relative bg-gray-800 rounded-lg overflow-hidden'>
                      <img
                        src={`/data${previewData.image_path}`}
                        alt='Image with overlay applied'
                        className='w-full h-auto'
                        onError={(e) => {
                          e.currentTarget.src =
                            "/assets/placeholder-overlay.jpg"
                        }}
                      />
                    </div>
                    <p className='text-xs text-muted-foreground mt-2'>
                      Preview: {presetName}
                    </p>
                  </CardContent>
                </Card>
              </div>

              {/* Configuration Summary */}
              <Card className='bg-gray-900/30 border-gray-700'>
                <CardContent className='p-4'>
                  <h4 className='text-sm font-medium mb-3'>
                    Overlay Configuration
                  </h4>
                  <div className='grid md:grid-cols-2 gap-4 text-xs'>
                    <div>
                      <h5 className='font-medium text-gray-300 mb-2'>
                        Global Options
                      </h5>
                      <div className='space-y-1 text-muted-foreground'>
                        <div>
                          Opacity: {overlayConfig.globalSettings.opacity}%
                        </div>
                        <div>Font: {overlayConfig.globalSettings.font}</div>
                        <div>
                          Margins: {overlayConfig.globalSettings.xMargin}px ×{" "}
                          {overlayConfig.globalSettings.yMargin}px
                        </div>
                        {overlayConfig.globalSettings.dropShadow && (
                          <div>
                            Drop Shadow:{" "}
                            {overlayConfig.globalSettings.dropShadow}px
                          </div>
                        )}
                      </div>
                    </div>
                    <div>
                      <h5 className='font-medium text-gray-300 mb-2'>
                        Overlay Elements
                      </h5>
                      <div className='space-y-1 text-muted-foreground'>
                        {overlayConfig.overlayItems.map((item) => (
                          <div key={item.id}>
                            {item.position}: {item.type} (enabled:{" "}
                            {item.enabled ? "yes" : "no"})
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Loading State */}
          {isGenerating && (
            <Card className='bg-gray-900/30 border-gray-700'>
              <CardContent className='p-8'>
                <div className='flex flex-col items-center justify-center space-y-4'>
                  <Loader2 className='w-8 h-8 animate-spin text-purple' />
                  <div className='text-center'>
                    <h3 className='text-lg font-medium'>Generating Preview</h3>
                    <p className='text-sm text-muted-foreground mt-1'>
                      Applying overlay configuration to camera image...
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Instructions */}
          {!previewData && !isGenerating && !error && (
            <Alert className='border-cyan/30 bg-cyan/10'>
              <AlertCircle className='w-4 h-4 text-cyan' />
              <AlertDescription className='text-sm text-cyan'>
                Select a camera and click "Generate Preview" to see how your
                overlay configuration will look on real camera images.
              </AlertDescription>
            </Alert>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
