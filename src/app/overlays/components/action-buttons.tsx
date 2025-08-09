// src/app/overlays/components/action-buttons.tsx
"use client"

import { Button } from "@/components/ui/button"
import { Save, Loader2 } from "lucide-react"

interface ActionButtonsProps {
  isSaving: boolean
  presetName: string
  onCancel: () => void
  onSave: () => void
}

export function ActionButtons({
  isSaving,
  presetName,
  onCancel,
  onSave,
}: ActionButtonsProps) {
  return (
    <div className='flex justify-end items-center gap-3 pt-4 border-t border-gray-600/30'>
      <Button
        onClick={onCancel}
        variant='outline'
        className='border-gray-500/30 text-gray-300 hover:bg-gray-500/20'
      >
        Cancel
      </Button>

      <Button
        onClick={onSave}
        disabled={isSaving || !presetName.trim()}
        className='bg-purple/20 hover:bg-purple/30 text-white border border-purple/30'
      >
        {isSaving ? (
          <Loader2 className='w-4 h-4 mr-2 animate-spin' />
        ) : (
          <Save className='w-4 h-4 mr-2' />
        )}
        Save Preset
      </Button>
    </div>
  )
}
