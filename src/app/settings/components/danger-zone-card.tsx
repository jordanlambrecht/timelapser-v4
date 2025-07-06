// src/app/settings/components/danger-zone-card.tsx
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
import { ConfirmationDialog } from "@/components/ui/confirmation-dialog"
import { toast } from "@/lib/toast"
import {
  AlertTriangle,
  Trash2,
  RotateCcw,
  Image as ImageIcon,
} from "lucide-react"

export function DangerZoneCard() {
  // Danger zone confirmation dialogs state
  const [resetSystemConfirmOpen, setResetSystemConfirmOpen] = useState(false)
  const [resetSettingsConfirmOpen, setResetSettingsConfirmOpen] =
    useState(false)
  const [deleteAllCamerasConfirmOpen, setDeleteAllCamerasConfirmOpen] =
    useState(false)
  const [deleteAllImagesConfirmOpen, setDeleteAllImagesConfirmOpen] =
    useState(false)
  const [deleteAllTimelapsesConfirmOpen, setDeleteAllTimelapsesConfirmOpen] =
    useState(false)
  const [deleteAllThumbnailsConfirmOpen, setDeleteAllThumbnailsConfirmOpen] =
    useState(false)

  // Danger zone handlers
  const handleResetSystem = async () => {
    setResetSystemConfirmOpen(false)
    toast.warning("System reset not available", {
      description:
        "This feature requires additional safety measures to implement",
      duration: 5000,
    })
    // TODO: Implement actual system reset functionality
  }

  const handleDeleteAllCameras = async () => {
    setDeleteAllCamerasConfirmOpen(false)
    toast.warning("Bulk delete not available", {
      description: "Use individual camera deletion for safety",
      duration: 4000,
    })
    // TODO: Implement actual bulk camera deletion
  }

  const handleDeleteAllImages = async () => {
    setDeleteAllImagesConfirmOpen(false)
    toast.warning("Bulk image delete not available", {
      description:
        "This feature requires additional safety measures to implement",
      duration: 5000,
    })
    // TODO: Implement actual bulk image deletion
  }

  const handleDeleteAllTimelapses = async () => {
    setDeleteAllTimelapsesConfirmOpen(false)
    toast.warning("Bulk timelapse delete not available", {
      description: "Use individual timelapse deletion for safety",
      duration: 4000,
    })
    // TODO: Implement actual bulk timelapse deletion
  }

  const handleResetSettings = async () => {
    setResetSettingsConfirmOpen(false)
    toast.info("Resetting settings...", {
      description: "All settings will be restored to default values",
      duration: 3000,
    })
    // TODO: Implement actual settings reset functionality
  }

  const handleDeleteAllThumbnails = async () => {
    setDeleteAllThumbnailsConfirmOpen(false)
    
    toast.info("Deleting thumbnails...", {
      description: "All thumbnail images are being removed",
      duration: 3000,
    })

    try {
      const response = await fetch("/api/thumbnails/delete-all", {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
      })

      if (!response.ok) {
        throw new Error(`Failed to delete thumbnails: ${response.statusText}`)
      }

      const result = await response.json()

      if (result.success) {
        toast.success("Thumbnails deleted successfully!", {
          description: `Deleted ${result.data.deleted_files} files (${result.data.deleted_size_mb}MB) from ${result.data.cameras_processed} cameras`,
          duration: 5000,
        })
      } else {
        throw new Error(result.message || "Failed to delete thumbnails")
      }
    } catch (error) {
      console.error("Error deleting thumbnails:", error)
      toast.error("Failed to delete thumbnails", {
        description: error instanceof Error ? error.message : "An unknown error occurred",
        duration: 5000,
      })
    }
  }

  return (
    <>
      {/* Danger Zone - Full Width */}
      <Card className='transition-all duration-300 glass hover:glow border-red-500/30'>
        <CardHeader>
          <CardTitle className='flex items-center space-x-2 text-red-400'>
            <AlertTriangle className='w-5 h-5 text-red-500' />
            <span>Danger Zone</span>
            <Badge
              variant='secondary'
              className='ml-2 text-xs bg-yellow-500/20 text-yellow-300 border-yellow-500/30'
            >
              Not Implemented
            </Badge>
          </CardTitle>
          <CardDescription className='text-red-300/70'>
            Destructive actions that cannot be undone. Use with extreme caution.
          </CardDescription>
        </CardHeader>
        <CardContent className='space-y-4'>
          <div className='grid gap-4 md:grid-cols-2 lg:grid-cols-3'>
            <Button
              type='button'
              variant='destructive'
              size='sm'
              onClick={() => setResetSystemConfirmOpen(true)}
              className='bg-red-600/20 border border-red-500/30 text-red-400 hover:bg-red-500/30 hover:text-white'
            >
              <RotateCcw className='w-4 h-4 mr-2' />
              Reset Whole System
            </Button>
            <Button
              type='button'
              variant='destructive'
              size='sm'
              onClick={() => setResetSettingsConfirmOpen(true)}
              className='bg-orange-600/20 border border-orange-500/30 text-orange-400 hover:bg-orange-500/30 hover:text-white'
            >
              <RotateCcw className='w-4 h-4 mr-2' />
              Reset Settings
            </Button>
            <Button
              type='button'
              variant='destructive'
              size='sm'
              onClick={() => setDeleteAllCamerasConfirmOpen(true)}
              className='bg-red-600/20 border border-red-500/30 text-red-400 hover:bg-red-500/30 hover:text-white'
            >
              <Trash2 className='w-4 h-4 mr-2' />
              Delete All Cameras
            </Button>
            <Button
              type='button'
              variant='destructive'
              size='sm'
              onClick={() => setDeleteAllImagesConfirmOpen(true)}
              className='bg-red-600/20 border border-red-500/30 text-red-400 hover:bg-red-500/30 hover:text-white'
            >
              <ImageIcon className='w-4 h-4 mr-2' />
              Delete All Images
            </Button>
            <Button
              type='button'
              variant='destructive'
              size='sm'
              onClick={() => setDeleteAllTimelapsesConfirmOpen(true)}
              className='bg-red-600/20 border border-red-500/30 text-red-400 hover:bg-red-500/30 hover:text-white'
            >
              <Trash2 className='w-4 h-4 mr-2' />
              Delete All Timelapses
            </Button>
            <Button
              type='button'
              variant='destructive'
              size='sm'
              onClick={() => setDeleteAllThumbnailsConfirmOpen(true)}
              className='bg-red-600/20 border border-red-500/30 text-red-400 hover:bg-red-500/30 hover:text-white'
            >
              <ImageIcon className='w-4 h-4 mr-2' />
              Delete All Thumbnails
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Reset System Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={resetSystemConfirmOpen}
        onClose={() => setResetSystemConfirmOpen(false)}
        onConfirm={handleResetSystem}
        title='Reset Whole System'
        description='This will delete ALL data including cameras, timelapses, images, and settings. This action CANNOT be undone!'
        confirmLabel='Yes, Reset Everything'
        cancelLabel='Cancel'
        variant='danger'
        icon={<RotateCcw className='w-6 h-6' />}
      />

      {/* Delete All Cameras Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={deleteAllCamerasConfirmOpen}
        onClose={() => setDeleteAllCamerasConfirmOpen(false)}
        onConfirm={handleDeleteAllCameras}
        title='Delete All Cameras'
        description='This will permanently delete all camera configurations and their associated data. This action cannot be undone!'
        confirmLabel='Yes, Delete All Cameras'
        cancelLabel='Cancel'
        variant='danger'
        icon={<Trash2 className='w-6 h-6' />}
      />

      {/* Delete All Images Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={deleteAllImagesConfirmOpen}
        onClose={() => setDeleteAllImagesConfirmOpen(false)}
        onConfirm={handleDeleteAllImages}
        title='Delete All Image Captures'
        description='This will permanently delete all captured images from all cameras and timelapses. This action cannot be undone!'
        confirmLabel='Yes, Delete All Images'
        cancelLabel='Cancel'
        variant='danger'
        icon={<ImageIcon className='w-6 h-6' />}
      />

      {/* Delete All Timelapses Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={deleteAllTimelapsesConfirmOpen}
        onClose={() => setDeleteAllTimelapsesConfirmOpen(false)}
        onConfirm={handleDeleteAllTimelapses}
        title='Delete All Timelapses'
        description='This will permanently delete all timelapse configurations and their associated data. This action cannot be undone!'
        confirmLabel='Yes, Delete All Timelapses'
        cancelLabel='Cancel'
        variant='danger'
        icon={<Trash2 className='w-6 h-6' />}
      />

      {/* Reset Settings Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={resetSettingsConfirmOpen}
        onClose={() => setResetSettingsConfirmOpen(false)}
        onConfirm={handleResetSettings}
        title='Reset All Settings'
        description='This will reset all application settings to their default values. This action cannot be undone!'
        confirmLabel='Yes, Reset Settings'
        cancelLabel='Cancel'
        variant='warning'
        icon={<RotateCcw className='w-6 h-6' />}
      />

      {/* Delete All Thumbnails Confirmation Dialog */}
      <ConfirmationDialog
        isOpen={deleteAllThumbnailsConfirmOpen}
        onClose={() => setDeleteAllThumbnailsConfirmOpen(false)}
        onConfirm={handleDeleteAllThumbnails}
        title='Delete All Thumbnails'
        description='This will permanently delete all thumbnail images. Original captures will remain untouched. This action cannot be undone!'
        confirmLabel='Yes, Delete All Thumbnails'
        cancelLabel='Cancel'
        variant='warning'
        icon={<ImageIcon className='w-6 h-6' />}
      />
    </>
  )
}
