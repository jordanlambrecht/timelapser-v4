// src/app/overlays/components/preset-header.tsx
"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Edit, Trash2 } from "lucide-react"
import { cn } from "@/lib/utils"
import type { OverlayItem, OverlayPreset } from "@/hooks/use-overlay-presets"
import { getOverlayPositions, GridPositionIcon } from "./grid-position-icon"

interface PresetHeaderProps {
  presetName: string
  presetDescription: string
  onNameChange: (name: string) => void
  onDescriptionChange: (description: string) => void
  onDelete?: () => void
  currentPreset?: OverlayPreset | null
  overlayItems: OverlayItem[]
}

export function PresetHeader({
  presetName,
  presetDescription,
  onNameChange,
  onDescriptionChange,
  onDelete,
  currentPreset,
  overlayItems,
}: PresetHeaderProps) {
  const [isEditingName, setIsEditingName] = useState(false)
  const [isEditingDescription, setIsEditingDescription] = useState(false)

  return (
    <div className='space-y-2 flex flex-row gap-x-5'>
      <GridPositionIcon positions={getOverlayPositions(overlayItems)} />
      <div className='flex flex-col justify-between h-full'>
        <div className='flex items-center gap-3'>
          {isEditingName ? (
            <Input
              value={presetName}
              onChange={(e) => onNameChange(e.target.value)}
              onBlur={() => setIsEditingName(false)}
              onKeyDown={(e) => {
                if (e.key === "Enter") setIsEditingName(false)
                if (e.key === "Escape") {
                  onNameChange(presetName)
                  setIsEditingName(false)
                }
              }}
              className='text-4xl font-bold bg-transparent border-none p-0 h-auto text-white focus:ring-2 focus:ring-purple/50'
              autoFocus
            />
          ) : (
            <h1
              className='text-4xl font-bold gradient-text cursor-pointer hover:opacity-80 transition-opacity align-top'
              onClick={() => setIsEditingName(true)}
            >
              {presetName || "New Overlay Preset"}
            </h1>
          )}

          <Button
            variant='ghost'
            size='sm'
            onClick={() => setIsEditingName(true)}
            className='text-gray-400 hover:text-white p-1'
          >
            <Edit className='w-4 h-4' />
          </Button>

          {/* Delete Preset Button */}
          {currentPreset && onDelete && (
            <Button
              variant='ghost'
              size='sm'
              onClick={onDelete}
              className='text-red-400 hover:text-red-300 p-1 ml-auto'
            >
              <Trash2 className='w-4 h-4' />
            </Button>
          )}
        </div>

        <div
          className={cn(
            "text-muted-foreground cursor-pointer transition-all",
            isEditingDescription
              ? "bg-gray-800/50 rounded p-2"
              : "hover:bg-gray-800/30 hover:rounded p-2"
          )}
          onClick={() => setIsEditingDescription(true)}
        >
          {isEditingDescription ? (
            <Input
              value={presetDescription}
              onChange={(e) => onDescriptionChange(e.target.value)}
              onBlur={() => setIsEditingDescription(false)}
              onKeyDown={(e) => {
                if (e.key === "Enter") setIsEditingDescription(false)
                if (e.key === "Escape") {
                  onDescriptionChange(presetDescription)
                  setIsEditingDescription(false)
                }
              }}
              placeholder='Add a description...'
              className='bg-transparent border-none p-0 h-auto text-gray-300 focus:ring-2 focus:ring-purple/50'
              autoFocus
            />
          ) : (
            <p>{presetDescription || "Click to add a description..."}</p>
          )}
        </div>
      </div>
    </div>
  )
}
