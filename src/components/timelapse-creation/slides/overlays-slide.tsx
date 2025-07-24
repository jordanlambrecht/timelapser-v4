// src/components/timelapse-creation/slides/overlays-slide.tsx
"use client"

import { useState, useEffect } from "react"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Camera, Image as ImageIcon, Loader2 } from "lucide-react"
import { useOverlayPresets } from "@/hooks/use-overlay-presets"
import type { TimelapseForm } from "../timelapse-creation-modal"

interface OverlaysSlideProps {
  form: TimelapseForm
  updateForm: (updates: Partial<TimelapseForm>) => void
}

export function OverlaysSlide({
  form,
  updateForm,
}: OverlaysSlideProps) {
  const [testImage, setTestImage] = useState<string | null>(null)
  const [isCapturingTest, setIsCapturingTest] = useState(false)
  const { presets, loading, error, fetchPresets } = useOverlayPresets()

  // Fetch presets when the overlay slide is first rendered
  useEffect(() => {
    fetchPresets()
  }, [])

  const handleTestImageCapture = async () => {
    setIsCapturingTest(true)
    try {
      // TODO: Implement actual camera test image capture
      // For now, simulate loading delay
      await new Promise(resolve => setTimeout(resolve, 1500))
      
      // Mock test image URL - would be actual camera image
      setTestImage("/api/placeholder-camera-image.jpg")
    } catch (error) {
      console.error("Failed to capture test image:", error)
    } finally {
      setIsCapturingTest(false)
    }
  }

  const selectedPreset = presets.find(preset => preset.id === form.overlayPresetId)

  return (
    <div className="px-1 space-y-6">
      <div className="text-center">
        <h3 className="text-xl font-semibold text-white mb-2">Overlays</h3>
        <p className="text-grey-light/70">Select overlay preset and preview the result</p>
      </div>

      {/* Overlay Enable/Disable Toggle */}
      <div className="flex items-center justify-between p-4 glass border border-purple-muted/30 rounded-lg">
        <div>
          <Label className="text-white font-medium">Enable Overlays</Label>
          <p className="text-grey-light/60 text-sm">Add informational overlays to your timelapse videos</p>
        </div>
        <Switch
          checked={form.overlayEnabled}
          onCheckedChange={(checked) => updateForm({ overlayEnabled: checked })}
        />
      </div>

      {form.overlayEnabled && (
        <>
          {/* Preset Selection */}
          <div className="space-y-3">
            <Label className="text-white font-medium">Overlay Preset</Label>
            <Select
              value={form.overlayPresetId?.toString() || ""}
              onValueChange={(value) => updateForm({ overlayPresetId: value ? parseInt(value) : null })}
              disabled={loading}
            >
              <SelectTrigger className="glass border-purple-muted/30 text-white">
                {loading ? (
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Loading presets...</span>
                  </div>
                ) : (
                  <SelectValue placeholder="Choose an overlay preset..." />
                )}
              </SelectTrigger>
              <SelectContent className="glass border-purple-muted/30">
                {loading ? (
                  <div className="p-2 text-center text-grey-light/60">
                    <Loader2 className="h-4 w-4 animate-spin mx-auto" />
                  </div>
                ) : error ? (
                  <div className="p-2 text-center text-red-400">
                    Failed to load presets
                  </div>
                ) : presets.length === 0 ? (
                  <div className="p-2 text-center text-grey-light/60">
                    No presets available
                  </div>
                ) : (
                  presets.map((preset) => (
                    <SelectItem key={preset.id} value={preset.id.toString()}>
                      <div>
                        <div className="font-medium text-white">{preset.name}</div>
                        <div className="text-sm text-grey-light/60">{preset.description}</div>
                      </div>
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>

          {/* Test Image Capture */}
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <Label className="text-white font-medium">Preview with Test Image</Label>
              <Button
                variant="outline"
                size="sm"
                onClick={handleTestImageCapture}
                disabled={isCapturingTest}
                className="border-purple-muted/30 text-grey-light hover:bg-purple-dark hover:border-purple-muted hover:text-white"
              >
                <Camera className="w-4 h-4 mr-2" />
                {isCapturingTest ? "Capturing..." : "Test Image"}
              </Button>
            </div>
            
            {/* Preview Area */}
            <div className="relative glass border border-purple-muted/30 rounded-lg aspect-video bg-purple-dark/20 overflow-hidden">
              {testImage ? (
                <div className="relative w-full h-full">
                  {/* TODO: Replace with actual image and overlay rendering */}
                  <div className="absolute inset-0 bg-gradient-to-br from-purple-dark/40 to-cyan-dark/40" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="text-center">
                      <ImageIcon className="w-12 h-12 text-white/60 mx-auto mb-2" />
                      <p className="text-white/80 font-medium">Test Image Captured</p>
                      {selectedPreset && (
                        <p className="text-grey-light/60 text-sm mt-1">
                          Showing "{selectedPreset.name}" preset
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center">
                    <Camera className="w-12 h-12 text-white/40 mx-auto mb-2" />
                    <p className="text-white/60">Click "Test Image" to capture a preview</p>
                    <p className="text-grey-light/40 text-sm mt-1">
                      Preview how overlays will look on your camera feed
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}