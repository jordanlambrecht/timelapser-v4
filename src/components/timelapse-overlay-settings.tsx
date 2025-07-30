// src/components/timelapse-overlay-settings.tsx
"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { 
  Layers, 
  Settings, 
  Eye, 
  Save, 
  Trash2, 
  Plus,
  AlertCircle,
  CheckCircle,
  Loader2,
  Copy,
  RefreshCw
} from "lucide-react"
import { useTimelapseOverlayConfig } from "@/hooks/use-timelapse-overlay-config"
import { useOverlayPresets } from "@/hooks/use-overlay-presets"
import { OverlayConfigurationEditor } from "@/components/overlay-configuration-editor"
import { OverlayPreviewModal } from "@/components/overlay-preview-modal"
import { useOverlaySSE } from "@/hooks/use-overlay-sse"
import { toast } from "sonner"

interface TimelapseOverlaySettingsProps {
  timelapseId: number
  timelapseName?: string
}

export function TimelapseOverlaySettings({ timelapseId, timelapseName }: TimelapseOverlaySettingsProps) {
  const [showEditor, setShowEditor] = useState(false)
  const [showPreview, setShowPreview] = useState(false)
  const [selectedPresetId, setSelectedPresetId] = useState<string>("")

  // Hooks
  const {
    config,
    loading,
    error,
    createConfig,
    updateConfig,
    deleteConfig,
    hasConfig,
    fetchConfig
  } = useTimelapseOverlayConfig(timelapseId)

  const { presets, loading: presetsLoading } = useOverlayPresets()
  const { overlayGenerationInProgress } = useOverlaySSE()

  const [currentConfig, setCurrentConfig] = useState<any>(null)
  const [saving, setSaving] = useState(false)
  const [reprocessing, setReprocessing] = useState(false)

  // Initialize current config when loaded
  useEffect(() => {
    if (config) {
      setCurrentConfig(config.overlay_config)
    }
  }, [config])

  const handleApplyPreset = async () => {
    if (!selectedPresetId) return

    const preset = presets.find(p => p.id === parseInt(selectedPresetId))
    if (!preset) return

    setCurrentConfig(preset.overlay_config)
    toast.success(`Applied "${preset.name}" preset configuration`)
  }

  const handleSaveConfig = async () => {
    if (!currentConfig) return

    setSaving(true)
    try {
      const configData = { overlay_config: currentConfig }
      
      if (hasConfig) {
        await updateConfig(configData)
      } else {
        await createConfig(configData)
      }
      
      await fetchConfig() // Refresh the config
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteConfig = async () => {
    if (!confirm("Are you sure you want to delete the overlay configuration for this timelapse?")) {
      return
    }

    await deleteConfig()
    setCurrentConfig(null)
    setShowEditor(false)
  }

  const handleReprocessOverlays = async () => {
    setReprocessing(true)
    try {
      const response = await fetch(`/api/timelapses/${timelapseId}/overlays/reprocess`, {
        method: "POST"
      })

      if (response.ok) {
        toast.success("Started overlay reprocessing for this timelapse", {
          description: "Check real-time updates for progress"
        })
      } else {
        throw new Error("Failed to start reprocessing")
      }
    } catch (error) {
      toast.error("Failed to start overlay reprocessing")
    } finally {
      setReprocessing(false)
    }
  }

  const isGenerating = overlayGenerationInProgress.size > 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Layers className="w-6 h-6 text-purple" />
          <div>
            <h2 className="text-xl font-semibold">Overlay Configuration</h2>
            <p className="text-sm text-muted-foreground">
              Configure overlay elements for {timelapseName || `Timelapse #${timelapseId}`}
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          {hasConfig && (
            <Badge variant="outline" className="border-green-500/30 text-green-400">
              <CheckCircle className="w-3 h-3 mr-1" />
              Configured
            </Badge>
          )}
          {isGenerating && (
            <Badge variant="outline" className="border-purple/30 text-purple">
              <Loader2 className="w-3 h-3 mr-1 animate-spin" />
              Generating
            </Badge>
          )}
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <Alert className="border-red-500/30 bg-red-500/10">
          <AlertCircle className="w-4 h-4 text-red-500" />
          <AlertDescription className="text-sm text-red-500">
            {error}
          </AlertDescription>
        </Alert>
      )}

      {/* Loading State */}
      {loading ? (
        <Card className="bg-gray-900/50 border-gray-700">
          <CardContent className="p-8">
            <div className="flex items-center justify-center space-x-3">
              <Loader2 className="w-6 h-6 animate-spin text-purple" />
              <span>Loading overlay configuration...</span>
            </div>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Configuration Status */}
          <Card className="bg-gray-900/50 border-gray-700">
            <CardHeader>
              <CardTitle className="text-lg flex items-center space-x-2">
                <Settings className="w-5 h-5 text-cyan" />
                <span>Configuration Status</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {hasConfig ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-green-400">
                        ✅ Overlay configuration is active
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Last updated: {new Date(config!.updated_at).toLocaleString()}
                      </p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Button
                        onClick={() => setShowPreview(true)}
                        size="sm"
                        variant="outline"
                        className="border-cyan/30 text-cyan hover:bg-cyan/10"
                      >
                        <Eye className="w-4 h-4 mr-2" />
                        Preview
                      </Button>
                      <Button
                        onClick={() => setShowEditor(true)}
                        size="sm"
                        className="bg-gradient-to-r from-purple to-cyan hover:from-purple/90 hover:to-cyan/90"
                      >
                        <Settings className="w-4 h-4 mr-2" />
                        Edit
                      </Button>
                    </div>
                  </div>
                  <Separator />
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">Reprocess Overlays</p>
                      <p className="text-xs text-muted-foreground">
                        Apply current configuration to all images in this timelapse
                      </p>
                    </div>
                    <Button
                      onClick={handleReprocessOverlays}
                      disabled={reprocessing || isGenerating}
                      size="sm"
                      variant="outline"
                      className="border-purple/30 text-purple hover:bg-purple/10"
                    >
                      {reprocessing || isGenerating ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Processing...
                        </>
                      ) : (
                        <>
                          <RefreshCw className="w-4 h-4 mr-2" />
                          Reprocess
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="text-center py-6">
                  <Layers className="w-12 h-12 mx-auto mb-3 text-gray-500" />
                  <p className="text-sm font-medium mb-2">No overlay configuration</p>
                  <p className="text-xs text-muted-foreground mb-4">
                    Create a configuration to add overlays to this timelapse
                  </p>
                  <Button
                    onClick={() => setShowEditor(true)}
                    className="bg-gradient-to-r from-purple to-cyan hover:from-purple/90 hover:to-cyan/90"
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    Create Configuration
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Quick Setup with Presets */}
          <Card className="bg-gray-900/50 border-gray-700">
            <CardHeader>
              <CardTitle className="text-lg flex items-center space-x-2">
                <Copy className="w-5 h-5 text-purple" />
                <span>Quick Setup</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm font-medium mb-3">Apply from Preset</p>
                <div className="flex items-center space-x-3">
                  <Select 
                    value={selectedPresetId} 
                    onValueChange={setSelectedPresetId}
                    disabled={presetsLoading}
                  >
                    <SelectTrigger className="flex-1">
                      <SelectValue placeholder="Select a preset to apply..." />
                    </SelectTrigger>
                    <SelectContent>
                      {presets.map(preset => (
                        <SelectItem key={preset.id} value={preset.id.toString()}>
                          <div className="flex items-center space-x-2">
                            <span>{preset.name}</span>
                            {preset.is_builtin && (
                              <Badge variant="secondary" className="text-xs">
                                Built-in
                              </Badge>
                            )}
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    onClick={handleApplyPreset}
                    disabled={!selectedPresetId || presetsLoading}
                    size="sm"
                    variant="outline"
                    className="border-purple/30 text-purple hover:bg-purple/10"
                  >
                    Apply
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  This will load the preset configuration but won't save it until you click "Save Configuration"
                </p>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {/* Configuration Editor Modal */}
      {showEditor && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm">
          <div className="min-h-screen flex items-center justify-center p-4">
            <div className="w-full max-w-6xl max-h-[90vh] overflow-y-auto bg-black/95 backdrop-blur-xl border border-purple/30 rounded-2xl">
              <div className="p-6">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="text-xl font-semibold flex items-center space-x-2">
                      <Layers className="w-5 h-5 text-purple" />
                      <span className="gradient-text">
                        {hasConfig ? "Edit" : "Create"} Overlay Configuration
                      </span>
                    </h2>
                    <p className="text-sm text-muted-foreground mt-1">
                      Configure overlay elements for {timelapseName || `Timelapse #${timelapseId}`}
                    </p>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Button
                      onClick={() => setShowEditor(false)}
                      variant="outline"
                      size="sm"
                    >
                      Cancel
                    </Button>
                    {hasConfig && (
                      <Button
                        onClick={handleDeleteConfig}
                        variant="outline"
                        size="sm"
                        className="border-red-500/30 text-red-400 hover:bg-red-500/10"
                      >
                        <Trash2 className="w-4 h-4 mr-2" />
                        Delete Config
                      </Button>
                    )}
                  </div>
                </div>

                <OverlayConfigurationEditor
                  config={currentConfig}
                  onChange={setCurrentConfig}
                  onSave={handleSaveConfig}
                  onPreview={() => setShowPreview(true)}
                  saving={saving}
                />

                <div className="flex items-center justify-end space-x-3 mt-6 pt-6 border-t border-gray-700">
                  <Button
                    onClick={() => setShowEditor(false)}
                    variant="outline"
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleSaveConfig}
                    disabled={saving || !currentConfig}
                    className="bg-gradient-to-r from-purple to-cyan hover:from-purple/90 hover:to-cyan/90"
                  >
                    <Save className="w-4 h-4 mr-2" />
                    {saving ? "Saving..." : "Save Configuration"}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Preview Modal */}
      {showPreview && currentConfig && (
        <OverlayPreviewModal
          open={showPreview}
          onOpenChange={setShowPreview}
          overlayConfig={currentConfig}
          presetName={timelapseName || `Timelapse #${timelapseId}`}
        />
      )}
    </div>
  )
}