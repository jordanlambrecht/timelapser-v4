// src/components/edit-timelapse-modal.tsx
"use client"

import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  X,
  Edit2,
  Crop,
  Layers,
  Filter,
  Settings,
  Zap,
  BarChart3,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { CropResizeTab } from "./edit-timelapse-modal/crop-resize-tab"
import { OverlaysTab } from "./edit-timelapse-modal/overlays-tab"
import { FiltersTab } from "./edit-timelapse-modal/filters-tab"
import { ControlsTab } from "./edit-timelapse-modal/controls-tab"
import { ActionsTab } from "./edit-timelapse-modal/actions-tab"
import { StatsTab } from "./edit-timelapse-modal/stats-tab"
import { SettingsTab } from "./edit-timelapse-modal/settings-tab"

interface EditTimelapseModalProps {
  isOpen: boolean
  onClose: () => void
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
  onSave?: (updates: any) => void
}

export function EditTimelapseModal({
  isOpen,
  onClose,
  timelapse,
  cameraId,
  cameraName,
  onSave,
}: EditTimelapseModalProps) {
  const [activeTab, setActiveTab] = useState("crop")
  const [timelapseData, setTimelapseData] = useState({
    name: timelapse.name,
    // Add other timelapse settings here as needed
  })
  const [isEditingName, setIsEditingName] = useState(false)
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)

  const handleNameChange = (newName: string) => {
    setTimelapseData(prev => ({ ...prev, name: newName }))
    setHasUnsavedChanges(true)
  }

  const handleSave = () => {
    if (onSave) {
      onSave(timelapseData)
    }
    setHasUnsavedChanges(false)
    onClose()
  }

  const handleCancel = () => {
    if (hasUnsavedChanges) {
      if (confirm("You have unsaved changes. Are you sure you want to cancel?")) {
        setTimelapseData({ name: timelapse.name })
        setHasUnsavedChanges(false)
        onClose()
      }
    } else {
      onClose()
    }
  }

  const tabs = [
    {
      id: "crop",
      label: "CROP & RESIZE",
      icon: Crop,
      component: CropResizeTab,
    },
    {
      id: "overlays",
      label: "OVERLAYS",
      icon: Layers,
      component: OverlaysTab,
    },
    {
      id: "filters",
      label: "FILTERS",
      icon: Filter,
      component: FiltersTab,
    },
    {
      id: "controls",
      label: "CONTROLS",
      icon: Settings,
      component: SettingsTab,
    },
    {
      id: "actions",
      label: "ACTIONS",
      icon: Zap,
      component: ActionsTab,
    },
    {
      id: "stats",
      label: "STATS",
      icon: BarChart3,
      component: StatsTab,
    },
  ]

  const ActiveTabComponent = tabs.find(tab => tab.id === activeTab)?.component || CropResizeTab

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent 
        className="glass-opaque border-purple-muted max-w-6xl h-[90vh] flex flex-col p-0 overflow-hidden"
        onInteractOutside={(e) => {
          if (hasUnsavedChanges) {
            e.preventDefault()
          }
        }}
      >
        {/* Header */}
        <DialogHeader className="flex-shrink-0 p-6 pb-4 border-b border-purple-muted/30">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {isEditingName ? (
                <Input
                  value={timelapseData.name}
                  onChange={(e) => handleNameChange(e.target.value)}
                  onBlur={() => setIsEditingName(false)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      setIsEditingName(false)
                    } else if (e.key === "Escape") {
                      setTimelapseData(prev => ({ ...prev, name: timelapse.name }))
                      setIsEditingName(false)
                    }
                  }}
                  className="text-xl font-semibold bg-black/20 border-cyan/30 text-white"
                  autoFocus
                />
              ) : (
                <DialogTitle 
                  className="text-xl font-semibold text-white cursor-pointer hover:text-cyan transition-colors flex items-center gap-2"
                  onClick={() => setIsEditingName(true)}
                >
                  {timelapseData.name}
                  <Edit2 className="w-4 h-4 text-cyan/60" />
                </DialogTitle>
              )}
              {hasUnsavedChanges && (
                <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse" />
              )}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCancel}
              className="text-white hover:bg-failure/20 hover:text-failure"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </DialogHeader>

        {/* Tab Navigation */}
        <div className="flex-shrink-0 px-6 py-4 border-b border-purple-muted/20">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-6 glass-strong p-1 gap-1">
              {tabs.map((tab) => {
                const Icon = tab.icon
                return (
                  <TabsTrigger
                    key={tab.id}
                    value={tab.id}
                    className={cn(
                      "flex items-center gap-2 px-3 py-2 text-xs font-medium transition-all duration-300 rounded-md",
                      activeTab === tab.id
                        ? "bg-cyan text-black shadow-lg shadow-cyan/20"
                        : "text-grey-light hover:text-white hover:bg-cyan/20"
                    )}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="hidden sm:inline">{tab.label}</span>
                  </TabsTrigger>
                )
              })}
            </TabsList>
          </Tabs>
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-hidden">
          <Tabs value={activeTab} className="h-full">
            <TabsContent value={activeTab} className="h-full m-0 p-6 overflow-y-auto">
              <ActiveTabComponent
                timelapse={timelapse}
                cameraId={cameraId}
                cameraName={cameraName}
                onDataChange={() => setHasUnsavedChanges(true)}
              />
            </TabsContent>
          </Tabs>
        </div>

        {/* Footer */}
        <div className="flex-shrink-0 flex items-center justify-between p-6 pt-4 border-t border-purple-muted/30">
          <div className="text-sm text-grey-light">
            Camera: <span className="text-white font-medium">{cameraName}</span>
            {hasUnsavedChanges && (
              <span className="ml-2 text-yellow-400">• Unsaved changes</span>
            )}
          </div>
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={handleCancel}
              className="border-gray-600 text-white hover:bg-gray-700"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={!hasUnsavedChanges}
              className={cn(
                "transition-all duration-300",
                hasUnsavedChanges
                  ? "bg-cyan hover:bg-cyan-dark text-black shadow-lg shadow-cyan/20"
                  : "bg-gray-600 text-gray-400 cursor-not-allowed"
              )}
            >
              Done
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}