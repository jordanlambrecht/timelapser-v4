// src/app/overlays/components/overlay-presets-card.tsx
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
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Layers,
  Plus,
  Grid3X3,
  AlertCircle,
  Loader2,
} from "lucide-react"
import { OverlayPresetEditor } from "./overlay-preset-editor"
import { PresetListItem } from "./preset-list-item"
import { useOverlayPresets, type OverlayPreset } from "@/hooks/use-overlay-presets"
import { OverlayPreviewModal } from "@/components/overlay-preview-modal"

export function OverlayPresetsCard() {
  const [selectedPreset, setSelectedPreset] = useState<number | null>(null)
  const [showEditor, setShowEditor] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [previewPreset, setPreviewPreset] = useState<OverlayPreset | null>(null)
  const { presets, loading, error, createPreset, updatePreset, deletePreset } = useOverlayPresets()

  const handleCreateNew = () => {
    setSelectedPreset(null)
    setShowEditor(true)
  }

  const handleEditPreset = (presetId: number) => {
    setSelectedPreset(presetId)
    setShowEditor(true)
  }

  const handleDeletePreset = async (presetId: number) => {
    const preset = presets.find(p => p.id === presetId)
    if (preset?.is_builtin) {
      alert("Built-in presets cannot be deleted")
      return
    }
    
    if (confirm("Are you sure you want to delete this preset?")) {
      await deletePreset(presetId)
    }
  }

  const handlePreviewPreset = (presetId: number) => {
    const preset = presets.find(p => p.id === presetId)
    if (preset) {
      setPreviewPreset(preset)
      setShowPreview(true)
    }
  }

  const handleSavePreset = async (name: string, description: string, config: any) => {
    if (selectedPreset) {
      // Update existing preset
      await updatePreset(selectedPreset, {
        name,
        description,
        overlay_config: config
      })
    } else {
      // Create new preset
      await createPreset({
        name,
        description,
        overlay_config: config
      })
    }
    setShowEditor(false)
    setSelectedPreset(null)
  }

  const getPresetForEdit = (): OverlayPreset | null => {
    if (selectedPreset) {
      const preset = presets.find(p => p.id === selectedPreset)
      return preset || null
    }
    return null
  }

  return (
    <>
      <Card className="transition-all duration-300 glass hover:glow">
        <CardHeader>
        <CardTitle className="flex items-center space-x-2">
          <Layers className="w-5 h-5 text-purple" />
          <span>Overlay Presets</span>
          <Badge
            variant="secondary"
            className="ml-2 text-xs bg-purple/20 text-purple-light border-purple/30"
          >
            {loading ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              `${presets.length} Presets`
            )}
          </Badge>
        </CardTitle>
        <CardDescription>
          Create and manage overlay presets for timelapses. Configure text, weather data, and image overlays with custom positioning.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Create New Preset Button */}
        <div className="flex justify-between items-center">
          <div className="space-y-1">
            <h4 className="text-sm font-medium">Manage Presets</h4>
            <p className="text-xs text-muted-foreground">
              Create reusable overlay configurations for your timelapses
            </p>
          </div>
          <Button
            onClick={handleCreateNew}
            className="bg-gradient-to-r from-purple to-cyan hover:from-purple/90 hover:to-cyan/90 text-white font-medium"
          >
            <Plus className="w-4 h-4 mr-2" />
            Create New
          </Button>
        </div>

        <Separator />

        {/* Error Display */}
        {error && (
          <Alert className="border-red-500/30 bg-red-500/10">
            <AlertCircle className="w-4 h-4 text-red-500" />
            <AlertDescription className="text-sm text-red-500">
              {error}
            </AlertDescription>
          </Alert>
        )}

        {/* Presets List */}
        <div className="space-y-4">
          <div className="flex items-center space-x-2">
            <Grid3X3 className="w-4 h-4 text-cyan" />
            <h4 className="text-sm font-medium text-white">Available Presets</h4>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-purple" />
              <span className="ml-2 text-sm text-muted-foreground">Loading presets...</span>
            </div>
          ) : (
            <div className="grid gap-3">
              {presets.map((preset) => (
                <PresetListItem
                  key={preset.id}
                  preset={preset}
                  onEdit={handleEditPreset}
                  onDelete={handleDeletePreset}
                  onPreview={handlePreviewPreset}
                />
              ))}
              {presets.length === 0 && (
                <div className="text-center py-8">
                  <p className="text-sm text-muted-foreground">No overlay presets found.</p>
                  <p className="text-xs text-muted-foreground mt-1">Create your first preset to get started.</p>
                </div>
              )}
            </div>
          )}
        </div>

        <Separator />

        {/* Usage Information */}
        <Alert className="border-cyan/30 bg-cyan/10">
          <AlertCircle className="w-4 h-4 text-cyan" />
          <AlertDescription className="text-sm text-cyan">
            Built-in presets cannot be deleted but can be duplicated as custom presets. 
            Overlay presets work with any camera resolution and are applied after image capture.
          </AlertDescription>
        </Alert>
      </CardContent>
    </Card>

    {/* Preset Editor Modal */}
    <Dialog open={showEditor} onOpenChange={(open) => {
      setShowEditor(open)
      if (!open) setSelectedPreset(null)
    }}>
      <DialogContent className="!max-w-[95vw] !w-[95vw] !max-h-[95vh] !h-[90vh] overflow-y-auto bg-black/95 backdrop-blur-xl border-purple/30">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold flex items-center space-x-2">
            <Layers className="w-5 h-5 text-purple" />
            <span className="gradient-text">{selectedPreset ? "Edit Overlay Preset" : "Create New Overlay Preset"}</span>
          </DialogTitle>
          <DialogDescription className="text-muted-foreground">
            Configure overlay elements and their positions for your timelapse. You can add multiple overlay elements in different positions.
          </DialogDescription>
        </DialogHeader>
        <div className="mt-4 px-4">
          <OverlayPresetEditor
            preset={getPresetForEdit()}
            onSave={(name, description, config) => {
              handleSavePreset(name, description, config)
              setShowEditor(false)
            }}
            onCancel={() => setShowEditor(false)}
          />
        </div>
      </DialogContent>
    </Dialog>

    {/* Preview Modal */}
    {previewPreset && (
      <OverlayPreviewModal
        open={showPreview}
        onOpenChange={setShowPreview}
        overlayConfig={previewPreset.overlay_config}
        presetName={previewPreset.name}
      />
    )}
    </>
  )
}