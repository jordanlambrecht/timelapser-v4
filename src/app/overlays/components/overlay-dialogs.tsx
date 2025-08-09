// src/app/overlays/components/overlay-dialogs.tsx
"use client"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"

interface NameDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  presetName: string
  presetDescription: string
  onNameChange: (name: string) => void
  onDescriptionChange: (description: string) => void
  onSave: () => void
}

export function NameDialog({
  open,
  onOpenChange,
  presetName,
  presetDescription,
  onNameChange,
  onDescriptionChange,
  onSave
}: NameDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Preset Name Required</DialogTitle>
          <DialogDescription>
            Please enter a name for your overlay preset before saving.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <Input
            placeholder="Enter preset name"
            value={presetName}
            onChange={(e) => onNameChange(e.target.value)}
            className="bg-gray-800/50 border-gray-600/50 text-white"
          />
          <Input
            placeholder="Enter description (optional)"
            value={presetDescription}
            onChange={(e) => onDescriptionChange(e.target.value)}
            className="bg-gray-800/50 border-gray-600/50 text-white"
          />
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            onClick={() => {
              if (presetName.trim()) {
                onOpenChange(false)
                onSave()
              }
            }}
            disabled={!presetName.trim()}
          >
            Save Preset
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

interface OverwriteDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  presetName: string
  onConfirm: () => void
}

export function OverwriteDialog({
  open,
  onOpenChange,
  presetName,
  onConfirm
}: OverwriteDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Overwrite Existing Preset?</DialogTitle>
          <DialogDescription>
            A preset with the name "{presetName}" already exists. Are you sure you want to overwrite it?
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            onClick={onConfirm}
            className="bg-red-500 hover:bg-red-600"
          >
            Yes, Overwrite
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}