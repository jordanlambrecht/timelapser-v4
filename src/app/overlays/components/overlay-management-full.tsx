// src/app/overlays/components/overlay-management-full.tsx
"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Layers } from "lucide-react"
import { toast } from "@/lib/toast"
import {
  useOverlayPresets,
  type OverlayPreset,
  type OverlayItem,
  type GlobalSettings,
  type OverlayConfig,
} from "@/hooks/use-overlay-presets"

// Import our new components
import { PresetHeader } from "./preset-header"
import { PreviewArea } from "./preview-area"
import { GlobalSettingsCard } from "./global-settings"
import { AddOverlayModal, OverlayEditor } from "./overlay-controls"
import { ActionButtons } from "./action-buttons"
import { NameDialog, OverwriteDialog } from "./overlay-dialogs"
import { GridPositionIcon } from "./grid-position-icon"
import { getDefaultSettings } from "./overlay-constants"

interface OverlayManagementProps {
  initialCameraId?: number
  initialPreset?: OverlayPreset | null
}

export function OverlayManagement({
  initialCameraId = 1,
  initialPreset = null,
}: OverlayManagementProps) {
  const router = useRouter()
  const [imageUrl, setImageUrl] = useState<string>("")
  const [isGrabbingFrame, setIsGrabbingFrame] = useState(false)
  const [selectedPosition, setSelectedPosition] = useState<string | null>(null)
  const [showAddOverlay, setShowAddOverlay] = useState(false)
  const [presetName, setPresetName] = useState(initialPreset?.name || "")
  const [presetDescription, setPresetDescription] = useState(
    initialPreset?.description || ""
  )
  const [isSaving, setIsSaving] = useState(false)
  const [overlaysEnabled, setOverlaysEnabled] = useState(true)
  const [showGrid, setShowGrid] = useState(false)
  const [showMargins, setShowMargins] = useState(false)
  const [globalsExpanded, setGlobalsExpanded] = useState(true)
  const [selectedCameraId, setSelectedCameraId] = useState(initialCameraId)
  const [cameras, setCameras] = useState<Array<{ id: number; name: string }>>(
    []
  )
  const [showNameDialog, setShowNameDialog] = useState(false)
  const [showOverwriteDialog, setShowOverwriteDialog] = useState(false)
  const [currentPreset, setCurrentPreset] = useState<OverlayPreset | null>(
    initialPreset
  )

  const { presets, loading, createPreset, updatePreset, deletePreset } =
    useOverlayPresets()

  // Global settings state
  const [globalSettings, setGlobalSettings] = useState<GlobalSettings>({
    opacity: 90,
    font: "Helvetica",
    xMargin: 15,
    yMargin: 15,
    backgroundColor: "#000000",
    backgroundOpacity: 50,
    fillColor: "#FFFFFF",
    dropShadow: 50,
    preset: "Custom Configuration",
  })

  // Overlay items state
  const [overlayItems, setOverlayItems] = useState<OverlayItem[]>([])

  // Initialize from existing preset if provided
  useEffect(() => {
    if (
      initialPreset?.overlay_config &&
      "globalSettings" in initialPreset.overlay_config
    ) {
      setGlobalSettings(initialPreset.overlay_config.globalSettings)
      setOverlayItems(initialPreset.overlay_config.overlayItems)
    }
  }, [initialPreset])

  // Initialize image URL and load cameras
  useEffect(() => {
    setImageUrl(
      `/api/cameras/${selectedCameraId}/latest-image/small?t=${Date.now()}`
    )

    const loadCameras = async () => {
      try {
        const response = await fetch("/api/cameras")
        if (response.ok) {
          const data = await response.json()
          setCameras(data)
        }
      } catch (error) {
        console.error("Failed to load cameras:", error)
      }
    }

    loadCameras()
  }, [selectedCameraId])

  // Camera handling
  const handleCameraChange = (cameraId: string) => {
    const id = cameraId === "placeholder" ? 1 : parseInt(cameraId)
    setSelectedCameraId(id)
    setImageUrl(`/api/cameras/${id}/latest-image/small?t=${Date.now()}`)
  }

  const handleGrabFreshFrame = async () => {
    setIsGrabbingFrame(true)
    try {
      const response = await fetch(
        `/api/overlays/fresh-photo/${selectedCameraId}`,
        {
          method: "POST",
        }
      )

      if (!response.ok) {
        // If fresh capture fails, fall back to refreshing the latest image
        console.warn(
          "Fresh capture failed, falling back to latest image refresh"
        )
        setImageUrl(
          `/api/cameras/${selectedCameraId}/latest-image/small?t=${Date.now()}`
        )
        toast.success("Image refreshed!")
        return
      }

      setTimeout(() => {
        setImageUrl(
          `/api/cameras/${selectedCameraId}/latest-image/small?t=${Date.now()}`
        )
        toast.success("Fresh frame captured!")
      }, 2000)
    } catch (error) {
      console.error("Failed to grab fresh frame:", error)
      // Fall back to refreshing the latest image
      setImageUrl(
        `/api/cameras/${selectedCameraId}/latest-image/small?t=${Date.now()}`
      )
      toast.error("Fresh capture failed, refreshed latest image instead")
    } finally {
      setIsGrabbingFrame(false)
    }
  }

  // Grid interaction handling
  const handleGridClick = (position: string) => {
    const existingOverlay = overlayItems.find(
      (item) => item.position === position
    )
    if (existingOverlay) {
      setSelectedPosition(position)
      setShowAddOverlay(false)
      setGlobalsExpanded(false)
    } else {
      setSelectedPosition(position)
      setShowAddOverlay(true)
      setGlobalsExpanded(false)
    }
  }

  const handleAddOverlay = (position: string, type: string) => {
    const newOverlay: OverlayItem = {
      id: `${type}_${Date.now()}`,
      type: type as any,
      position: position as any,
      enabled: true,
      settings: getDefaultSettings(type),
    }

    setOverlayItems((prev) => [...prev, newOverlay])
    setShowAddOverlay(false)
    setSelectedPosition(position)
    toast.success(`Overlay added successfully`)
  }

  const handleUpdateOverlay = (updatedOverlay: OverlayItem) => {
    setOverlayItems((prev) =>
      prev.map((item) =>
        item.id === updatedOverlay.id ? updatedOverlay : item
      )
    )
  }

  const handleRemoveOverlay = (position: string) => {
    setOverlayItems((prev) => prev.filter((item) => item.position !== position))
    if (selectedPosition === position) {
      setSelectedPosition(null)
    }
    toast.success("Overlay removed")
  }

  // Preset handling
  const handleDelete = async () => {
    if (!currentPreset) return

    if (confirm("Are you sure you want to delete this preset?")) {
      try {
        await deletePreset(currentPreset.id)
        toast.success("Preset deleted successfully")
        router.push("/overlays")
      } catch (error) {
        toast.error("Failed to delete preset")
      }
    }
  }

  const handleSaveAsPreset = async () => {
    if (!presetName.trim()) {
      setShowNameDialog(true)
      return
    }

    const existingPreset = presets.find(
      (p) => p.name.toLowerCase() === presetName.toLowerCase()
    )
    if (existingPreset && !currentPreset) {
      setShowOverwriteDialog(true)
      return
    }

    await savePreset()
  }

  const savePreset = async () => {
    setIsSaving(true)
    try {
      const overlayConfig: OverlayConfig = {
        globalSettings,
        overlayItems,
      }

      if (currentPreset) {
        await updatePreset(currentPreset.id, {
          name: presetName,
          description: presetDescription,
          overlay_config: overlayConfig,
        })
      } else {
        await createPreset({
          name: presetName,
          description: presetDescription,
          overlay_config: overlayConfig,
        })
      }

      toast.success("Preset saved successfully!")
      setPresetName("")
      setPresetDescription("")

      setTimeout(() => {
        router.push("/overlays")
      }, 1000)
    } catch (error) {
      console.error("Save preset error:", error)
      toast.error("Failed to save preset")
    } finally {
      setIsSaving(false)
      setShowOverwriteDialog(false)
      setShowNameDialog(false)
    }
  }

  const handleExport = async () => {
    try {
      const overlayConfig: OverlayConfig = { globalSettings, overlayItems }
      const dataStr = JSON.stringify(overlayConfig, null, 2)
      const dataBlob = new Blob([dataStr], { type: "application/json" })
      const url = URL.createObjectURL(dataBlob)
      const link = document.createElement("a")
      link.href = url
      link.download = `overlay-config-${Date.now()}.json`
      link.click()
      toast.success("Overlay configuration exported!")
    } catch (error) {
      toast.error("Failed to export configuration")
    }
  }

  const getOverlayAtPosition = (position: string) => {
    return overlayItems.find((item) => item.position === position)
  }

  return (
    <div className='space-y-6'>
      <Card className='transition-all duration-300 glass hover:glow'>
        <CardHeader>
          <CardTitle className='flex items-center justify-between'>
            {/* Preset Header */}
            <PresetHeader
              presetName={presetName}
              presetDescription={presetDescription}
              onNameChange={setPresetName}
              onDescriptionChange={setPresetDescription}
              onDelete={handleDelete}
              currentPreset={currentPreset}
              overlayItems={overlayItems}
            />
            {/* <div className='flex items-center space-x-2'>
              <GridPositionIcon overlayItems={overlayItems} />
              <Layers className='w-5 h-5 text-purple' />
              <span>Overlay Configuration</span>
            </div>
            <div className='flex items-center gap-2'>
              <span className='text-sm text-gray-400'>
                {overlayItems.length} overlay
                {overlayItems.length !== 1 ? "s" : ""}
              </span>
            </div> */}
          </CardTitle>
          {/* <CardDescription>
            Click grid positions to add overlays. Configure global settings and
            individual overlay properties.
          </CardDescription> */}
        </CardHeader>

        <CardContent>
          <div className='grid grid-cols-1 xl:grid-cols-3 gap-6'>
            {/* Left Column - Live Preview */}
            <div className='xl:col-span-2 space-y-4 relative'>
              <PreviewArea
                imageUrl={imageUrl}
                isGrabbingFrame={isGrabbingFrame}
                overlayItems={overlayItems}
                globalSettings={globalSettings}
                overlaysEnabled={overlaysEnabled}
                showGrid={showGrid}
                showMargins={showMargins}
                selectedPosition={selectedPosition}
                selectedCameraId={selectedCameraId}
                cameras={cameras}
                onGrabFreshFrame={handleGrabFreshFrame}
                onGridClick={handleGridClick}
                onRemoveOverlay={handleRemoveOverlay}
                onCameraChange={handleCameraChange}
                onOverlaysEnabledChange={setOverlaysEnabled}
                onShowGridChange={setShowGrid}
                onShowMarginsChange={setShowMargins}
                onExport={handleExport}
              />

              {/* Add Overlay Modal - Positioned over preview area */}
              {showAddOverlay && selectedPosition && (
                <div className='absolute inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 rounded-lg'>
                  <div className='w-full m-4 mx-4 mb-4'>
                    <AddOverlayModal
                      selectedPosition={selectedPosition}
                      onAddOverlay={handleAddOverlay}
                      onClose={() => setShowAddOverlay(false)}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Right Column - Controls */}
            <div className='space-y-4'>
              {/* Global Settings */}
              <GlobalSettingsCard
                globalSettings={globalSettings}
                onSettingsChange={setGlobalSettings}
                isExpanded={globalsExpanded}
                onToggleExpanded={() => setGlobalsExpanded(!globalsExpanded)}
              />

              {/* Selected Overlay Controls */}
              {selectedPosition &&
                getOverlayAtPosition(selectedPosition) &&
                !showAddOverlay && (
                  <OverlayEditor
                    overlay={getOverlayAtPosition(selectedPosition)!}
                    selectedPosition={selectedPosition}
                    onUpdateOverlay={handleUpdateOverlay}
                    onRemoveOverlay={handleRemoveOverlay}
                  />
                )}
            </div>
          </div>
        </CardContent>
        <CardContent>
          {/* Action Buttons */}
          <ActionButtons
            isSaving={isSaving}
            presetName={presetName}
            onCancel={() => router.push("/overlays")}
            onSave={handleSaveAsPreset}
          />
        </CardContent>
      </Card>

      {/* Dialogs */}
      <NameDialog
        open={showNameDialog}
        onOpenChange={setShowNameDialog}
        presetName={presetName}
        presetDescription={presetDescription}
        onNameChange={setPresetName}
        onDescriptionChange={setPresetDescription}
        onSave={handleSaveAsPreset}
      />

      <OverwriteDialog
        open={showOverwriteDialog}
        onOpenChange={setShowOverwriteDialog}
        presetName={presetName}
        onConfirm={savePreset}
      />
    </div>
  )
}
