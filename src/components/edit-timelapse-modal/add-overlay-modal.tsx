// src/components/edit-timelapse-modal/add-overlay-modal.tsx
"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Cloud,
  Image as ImageIcon,
  Hash,
  Calendar,
  Type,
  FileText,
  X,
  Activity,
} from "lucide-react"
import { cn } from "@/lib/utils"

interface AddOverlayModalProps {
  isOpen: boolean
  onClose: () => void
  onAdd: (overlayType: string) => void
}

interface OverlayType {
  id: string
  name: string
  icon: any
  color: string
  description: string
}

const overlayTypes: OverlayType[] = [
  {
    id: "weather",
    name: "Weather",
    icon: Cloud,
    color: "text-purple",
    description: "Display weather information and temperature"
  },
  {
    id: "watermark",
    name: "Watermark",
    icon: ImageIcon,
    color: "text-cyan",
    description: "Add logo or image watermark"
  },
  {
    id: "frame_number",
    name: "Frame Number",
    icon: Hash,
    color: "text-pink",
    description: "Show current frame number in sequence"
  },
  {
    id: "date_time",
    name: "Date & Time",
    icon: Calendar,
    color: "text-cyan",
    description: "Display capture date and time"
  },
  {
    id: "day_counter",
    name: "Day Counter",
    icon: Activity,
    color: "text-purple",
    description: "Count days since timelapse started"
  },
  {
    id: "custom_text",
    name: "Custom Text",
    icon: Type,
    color: "text-pink",
    description: "Add custom text overlay"
  },
  {
    id: "timelapse_name",
    name: "Timelapse Name",
    icon: FileText,
    color: "text-cyan",
    description: "Display the timelapse name"
  },
]

export function AddOverlayModal({ isOpen, onClose, onAdd }: AddOverlayModalProps) {
  const [selectedType, setSelectedType] = useState<string | null>(null)

  if (!isOpen) return null

  const handleAdd = () => {
    if (selectedType) {
      onAdd(selectedType)
      setSelectedType(null)
      onClose()
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/50 backdrop-blur-sm" 
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative bg-gray-900/95 border border-gray-600/30 rounded-xl p-6 max-w-md w-full mx-4 backdrop-blur-sm">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">Add New Overlay</h3>
          <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            className="text-gray-400 hover:text-white"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>
        
        {/* Overlay Types */}
        <div className="space-y-2 mb-6">
          {overlayTypes.map((type) => (
            <div
              key={type.id}
              className={cn(
                "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all duration-200",
                selectedType === type.id
                  ? "bg-purple/10 border-purple/30"
                  : "bg-black/20 border-gray-600/30 hover:border-gray-500/50 hover:bg-gray-800/50"
              )}
              onClick={() => setSelectedType(type.id)}
            >
              <type.icon className={cn("w-5 h-5", type.color)} />
              <div className="flex-1">
                <div className="text-white font-medium text-sm">{type.name}</div>
                <div className="text-gray-400 text-xs">{type.description}</div>
              </div>
              {selectedType === type.id && (
                <div className="w-2 h-2 rounded-full bg-purple" />
              )}
            </div>
          ))}
        </div>
        
        {/* Actions */}
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            onClick={onClose}
            className="flex-1 border-gray-500 text-gray-400 hover:text-white"
          >
            Cancel
          </Button>
          <Button
            onClick={handleAdd}
            disabled={!selectedType}
            className="flex-1 bg-purple hover:bg-purple/80 text-white disabled:opacity-50"
          >
            Add Overlay
          </Button>
        </div>
      </div>
    </div>
  )
}