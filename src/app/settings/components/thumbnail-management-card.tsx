"use client"

import { useState, useEffect } from "react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import {
  Layers,
  BarChart3,
  CheckCircle,
  Wrench,
  RefreshCw,
  Trash2,
  AlertTriangle,
  HardDrive,
  ImageIcon,
  Loader2,
  X,
  Activity,
  XCircle,
} from "lucide-react"
import { toast } from "@/lib/toast"
import { SuperSwitch } from "@/components/ui/switch"
import { useSettings } from "@/contexts/settings-context"
import { Label } from "@/components/ui/label"
import { ToggleGroup } from "@/components/ui/toggle-group"
import { ThumbnailRegenerationModal } from "@/components/thumbnail-regeneration-modal"

// Thumbnail API types based on master plan
interface ThumbnailStatistics {
  total_images: number
  images_with_thumbnails: number
  images_with_small: number
  images_without_thumbnails: number
  thumbnail_coverage_percentage: number
  total_thumbnail_storage_mb: number
  total_small_storage_mb: number
  avg_thumbnail_size_kb: number
  avg_small_size_kb: number
  last_updated: string
}

interface ThumbnailOperationResult {
  success: boolean
  message: string
  data?: {
    total_jobs?: number
    jobs_created?: number
    jobs_failed?: number
    orphaned_files_found?: number
    files_matched?: number
    files_deleted?: number
    database_records_updated?: number
    timelapses_affected?: number
    deleted_files?: number
    deleted_size_mb?: number
    cameras_processed?: number
    cleared_database_records?: number
    errors?: string[]
  }
  error_code?: string
}

interface RegenerationStatus {
  active: boolean
  progress: number
  total_images: number
  completed_images: number
  failed_images: number
  current_image_id?: number
  current_image_name?: string
  estimated_time_remaining_seconds?: number
  started_at?: string
  status_message: string
}

export function ThumbnailManagementCard({}) {
  const [statistics, setStatistics] = useState<ThumbnailStatistics | null>(null)
  const [loading, setLoading] = useState(false)
  const [operationInProgress, setOperationInProgress] = useState<string | null>(
    null
  )
  const [regenerationStatus, setRegenerationStatus] =
    useState<RegenerationStatus | null>(null)
  const [showResults, setShowResults] = useState<{
    operation: string
    result: ThumbnailOperationResult
  } | null>(null)
  const [showRegenerationModal, setShowRegenerationModal] = useState(false)

  const {
    enableThumbnailGeneration,
    smallGenerationMode,
    purgeSmalllsOnCompletion,
    setEnableThumbnailGeneration,
    setSmallGenerationMode,
    setPurgeSmalllsOnCompletion,
    saving,
  } = useSettings()

  // Handle small generation mode change with autosave
  const handleSmallGenerationModeChange = async (
    value: "disabled" | "latest" | "all"
  ) => {
    await setSmallGenerationMode(value)
  }

  // Load initial statistics
  useEffect(() => {
    loadStatistics()
  }, [])

  // Debug: Log when statistics change
  useEffect(() => {
    console.log("📊 Statistics state changed:", statistics)
    console.log("📊 Should show statistics section:", !!statistics)
    console.log("📊 Loading state:", loading)
  }, [statistics, loading])

  const loadStatistics = async () => {
    try {
      setLoading(true)
      console.log("🔍 Loading thumbnail statistics...")
      const response = await fetch("/api/thumbnails/stats")

      if (!response.ok) {
        throw new Error("Failed to load thumbnail statistics")
      }

      const statistics = await response.json()
      console.log("📊 Received statistics:", statistics)
      console.log("📊 Statistics type:", typeof statistics)
      console.log("📊 Statistics keys:", Object.keys(statistics))
      setStatistics(statistics)
      console.log("📊 State after setting:", statistics)
    } catch (error) {
      console.error("Error loading thumbnail statistics:", error)
      toast.error("Failed to load thumbnail statistics")
    } finally {
      setLoading(false)
    }
  }

  const verifyAllThumbnails = async () => {
    try {
      setOperationInProgress("verify")
      const response = await fetch("/api/thumbnails/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      })

      const result = await response.json()

      if (result.success) {
        toast.success("Thumbnail verification completed")
        setShowResults({ operation: "Verify All Thumbnails", result })
        await loadStatistics() // Refresh stats
      } else {
        toast.error(result.message || "Verification failed")
      }
    } catch (error) {
      console.error("Error verifying thumbnails:", error)
      toast.error("Failed to verify thumbnails")
    } finally {
      setOperationInProgress(null)
    }
  }

  const repairOrphanedThumbnails = async () => {
    try {
      setOperationInProgress("repair")
      const response = await fetch("/api/thumbnails/repair", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      })

      const result = await response.json()

      if (result.success) {
        toast.success("Orphaned thumbnail repair completed")
        setShowResults({ operation: "Repair Orphaned Thumbnails", result })
        await loadStatistics() // Refresh stats
      } else {
        toast.error(result.message || "Repair failed")
      }
    } catch (error) {
      console.error("Error repairing orphaned thumbnails:", error)
      toast.error("Failed to repair orphaned thumbnails")
    } finally {
      setOperationInProgress(null)
    }
  }

  const regenerateAllThumbnails = async () => {
    try {
      setOperationInProgress("regenerate")
      const response = await fetch("/api/thumbnails/regenerate-all", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      })

      const result = await response.json()

      if (result.success) {
        toast.success("Bulk thumbnail regeneration started")
        setShowResults({ operation: "Regenerate All Thumbnails", result })
        // Start polling for status updates
        pollRegenerationStatus()
      } else {
        toast.error(result.message || "Failed to start regeneration")
      }
    } catch (error) {
      console.error("Error starting bulk regeneration:", error)
      toast.error("Failed to start bulk regeneration")
    } finally {
      setOperationInProgress(null)
    }
  }

  const cancelRegeneration = async () => {
    try {
      const response = await fetch("/api/thumbnails/regenerate-all/cancel", {
        method: "POST",
      })

      const result = await response.json()

      if (result.success) {
        toast.info("Thumbnail regeneration cancelled")
        setRegenerationStatus(null)
      } else {
        toast.error("Failed to cancel regeneration")
      }
    } catch (error) {
      console.error("Error cancelling regeneration:", error)
      toast.error("Failed to cancel regeneration")
    }
  }

  const cleanupOrphanedFiles = async () => {
    try {
      setOperationInProgress("cleanup")
      const response = await fetch("/api/thumbnails/cleanup", {
        method: "DELETE",
      })

      const result = await response.json()

      if (result.success) {
        toast.success("Orphaned file cleanup completed")
        setShowResults({ operation: "Cleanup Orphaned Files", result })
        await loadStatistics() // Refresh stats
      } else {
        toast.error(result.message || "Cleanup failed")
      }
    } catch (error) {
      console.error("Error cleaning up orphaned files:", error)
      toast.error("Failed to cleanup orphaned files")
    } finally {
      setOperationInProgress(null)
    }
  }

  const deleteAllThumbnails = async () => {
    try {
      setOperationInProgress("deleteAll")
      const response = await fetch("/api/thumbnails/delete-all", {
        method: "DELETE",
      })

      const result = await response.json()

      if (result.success) {
        toast.success("All thumbnails deleted successfully")
        setShowResults({ operation: "Delete All Thumbnails", result })
        await loadStatistics() // Refresh stats
      } else {
        toast.error(result.message || "Delete all failed")
      }
    } catch (error) {
      console.error("Error deleting all thumbnails:", error)
      toast.error("Failed to delete all thumbnails")
    } finally {
      setOperationInProgress(null)
    }
  }

  const pollRegenerationStatus = async () => {
    try {
      const response = await fetch("/api/thumbnails/regenerate-all/status")
      const result = await response.json()

      if (result.success) {
        setRegenerationStatus(result.data)

        // Continue polling if still active
        if (result.data.active) {
          setTimeout(pollRegenerationStatus, 2000) // Poll every 2 seconds
        } else {
          // Refresh stats when complete
          await loadStatistics()
        }
      }
    } catch (error) {
      console.error("Error polling regeneration status:", error)
      // Continue polling despite errors
      if (regenerationStatus?.active) {
        setTimeout(pollRegenerationStatus, 2000)
      }
    }
  }

  const formatFileSize = (mb: number): string => {
    // Ensure we have a valid number
    const size = typeof mb === "number" && !isNaN(mb) ? mb : 0

    if (size >= 1024) {
      return `${(size / 1024).toFixed(1)} GB`
    }
    return `${size.toFixed(1)} MB`
  }

  const formatDuration = (seconds: number): string => {
    if (seconds < 60) return `${seconds}s`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}h ${minutes}m`
  }

  return (
    <>
      <Card className='glass border-purple-muted/30'>
        <CardHeader>
          <div className='flex items-center justify-between'>
            <div className='flex items-center space-x-3'>
              <div className='p-2 bg-gradient-to-br from-pink/20 to-purple/20 rounded-lg'>
                <Layers className='w-5 h-5 text-pink-light' />
              </div>
              <div>
                <CardTitle className='text-white flex items-center space-x-2'>
                  <span>Thumbnail System Management</span>
                  {saving && (
                    <Badge
                      variant='secondary'
                      className='text-xs bg-blue-500/20 text-blue-300 border-blue-500/30'
                    >
                      <Loader2 className='w-3 h-3 animate-spin mr-1' />
                      Saving...
                    </Badge>
                  )}
                </CardTitle>
                <CardDescription>
                  System-wide thumbnail operations and maintenance
                </CardDescription>
              </div>
            </div>

            <Button
              onClick={loadStatistics}
              disabled={loading}
              variant='outline'
              size='sm'
              className='border-purple-muted/40 hover:bg-purple/20 text-white'
            >
              {loading ? (
                <Loader2 className='w-4 h-4 animate-spin' />
              ) : (
                <RefreshCw className='w-4 h-4' />
              )}
            </Button>
          </div>
        </CardHeader>
        <Separator className='bg-purple-muted/20' />
        <CardContent className='space-y-6'>
          {/* GENERATION TOGGLES */}
          <div className='my-6 flex flex-row justify-between'>
            <div>
              <Label
                htmlFor='thumbnails'
                className='text-sm font-medium flex items-center space-x-2'
              >
                <ImageIcon className='w-4 h-4 text-purple-light' />
                <h3>Generate Thumbnails</h3>
              </Label>
              <p className='text-xs text-muted-foreground'>
                Automatically creates 200×150px thumbnails alongside full
                captures
              </p>
            </div>
            {/* Master enable/disable */}
            <SuperSwitch
              variant='labeled'
              id='thumbnails'
              falseLabel='disabled'
              trueLabel='enabled'
              checked={enableThumbnailGeneration}
              onCheckedChange={(value: boolean) =>
                setEnableThumbnailGeneration(value)
              }
            />
          </div>

          {/* Small Generation Mode - only show if thumbnails are enabled */}
          {enableThumbnailGeneration && (
            <div className='my-6 flex flex-row justify-between'>
              <div>
                <Label
                  htmlFor='smallGenerationMode'
                  className='text-sm font-medium flex items-center space-x-2'
                >
                  <ImageIcon className='w-4 h-4 text-blue-400' />
                  <h3>Small Image Generation</h3>
                </Label>
                <p className='text-xs text-muted-foreground'>
                  Control when to create 800×600 small images alongside
                  thumbnails
                </p>
              </div>
              <ToggleGroup
                options={[
                  { label: "Disabled", value: "disabled" },
                  { label: "Latest Only", value: "latest" },
                  { label: "All Captures", value: "all" },
                ]}
                value={smallGenerationMode}
                onValueChange={(value) =>
                  handleSmallGenerationModeChange(
                    value as "disabled" | "latest" | "all"
                  )
                }
                label='Small Image Mode'
                colorTheme='cyan'
                id='smallGenerationMode'
                borderFaded={true}
                borderNone={true}
                size='lg'
              />
            </div>
          )}

          {/* Purge Smalls on Completion Toggle - only show if thumbnails are enabled */}
          {enableThumbnailGeneration && (
            <div className='my-6 flex flex-row justify-between'>
              <div>
                <Label
                  htmlFor='purgeSmalls'
                  className='text-sm font-medium flex items-center space-x-2'
                >
                  <ImageIcon className='w-4 h-4 text-orange-400' />
                  <h3>Auto-purge Small Images</h3>
                </Label>
                <p className='text-xs text-muted-foreground'>
                  Automatically delete small images after timelapse completion
                  to save storage
                </p>
              </div>
              <SuperSwitch
                variant='labeled'
                id='purgeSmalls'
                falseLabel='keep'
                trueLabel='purge'
                checked={purgeSmalllsOnCompletion}
                onCheckedChange={(value: boolean) =>
                  setPurgeSmalllsOnCompletion(value)
                }
              />
            </div>
          )}

          <Separator className='bg-purple-muted/20' />

          {/* Loading State */}
          {loading && (
            <div className='flex items-center justify-center p-8'>
              <Loader2 className='w-8 h-8 animate-spin text-purple' />
              <span className='ml-3 text-grey-light'>
                Loading statistics...
              </span>
            </div>
          )}

          {/* Error State */}
          {!loading && !statistics && (
            <div className='flex items-center justify-center p-8 bg-red-500/10 border border-red-500/20 rounded-lg'>
              <AlertTriangle className='w-6 h-6 text-red-400' />
              <span className='ml-3 text-red-400'>
                Failed to load statistics. Try clicking the refresh button.
              </span>
            </div>
          )}

          {/* Comprehensive Statistics Display */}
          {statistics && (
            <div className='space-y-6'>
              <div className='flex items-center space-x-2'>
                <BarChart3 className='w-4 h-4 text-cyan' />
                <h4 className='text-sm font-medium text-white'>
                  Thumbnail System Statistics
                </h4>
              </div>

              {/* Primary Statistics - Highlighted */}
              <div className='grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-blue-500/10 border-2 border-blue-500/30 rounded-lg'>
                <div className='bg-black/30 p-4 rounded-lg border border-blue-500/20'>
                  <div className='text-2xl font-bold text-blue-300 mb-1'>
                    {statistics.total_images.toLocaleString()}
                  </div>
                  <div className='text-sm text-grey-light/70'>Total Images</div>
                </div>

                <div className='bg-black/30 p-4 rounded-lg border border-green-500/20'>
                  <div className='text-2xl font-bold text-green-400 mb-1'>
                    {statistics.images_with_thumbnails.toLocaleString()}
                  </div>
                  <div className='text-sm text-grey-light/70'>
                    With Thumbnails
                  </div>
                </div>

                <div className='bg-black/30 p-4 rounded-lg border border-red-500/20'>
                  <div className='text-2xl font-bold text-red-400 mb-1'>
                    {statistics.images_without_thumbnails.toLocaleString()}
                  </div>
                  <div className='text-sm text-grey-light/70'>
                    Missing Thumbnails
                  </div>
                </div>
              </div>

              {/* Detailed Statistics Grid */}
              <div className='grid grid-cols-2 md:grid-cols-4 gap-4'>
                <div className='space-y-2 p-3 glass rounded-lg border border-purple-muted/20'>
                  <div className='flex items-center space-x-2'>
                    <Layers className='w-4 h-4 text-pink' />
                    <span className='text-xs text-grey-light/70'>Coverage</span>
                  </div>
                  <div className='text-lg font-bold text-white'>
                    {statistics.thumbnail_coverage_percentage.toFixed(1)}%
                  </div>
                  <Progress
                    value={statistics.thumbnail_coverage_percentage}
                    className='h-1'
                  />
                </div>

                <div className='space-y-2 p-3 glass rounded-lg border border-purple-muted/20'>
                  <div className='flex items-center space-x-2'>
                    <HardDrive className='w-4 h-4 text-yellow' />
                    <span className='text-xs text-grey-light/70'>Storage</span>
                  </div>
                  <div className='text-lg font-bold text-white'>
                    {formatFileSize(
                      statistics.total_thumbnail_storage_mb +
                        statistics.total_small_storage_mb
                    )}
                  </div>
                </div>

                <div className='space-y-2 p-3 glass rounded-lg border border-purple-muted/20'>
                  <div className='flex items-center space-x-2'>
                    <ImageIcon className='w-4 h-4 text-cyan' />
                    <span className='text-xs text-grey-light/70'>
                      With Small Images
                    </span>
                  </div>
                  <div className='text-lg font-bold text-white'>
                    {statistics.images_with_small.toLocaleString()}
                  </div>
                </div>

                <div className='space-y-2 p-3 glass rounded-lg border border-purple-muted/20'>
                  <div className='flex items-center space-x-2'>
                    <Activity className='w-4 h-4 text-success' />
                    <span className='text-xs text-grey-light/70'>
                      Avg Thumbnail Size
                    </span>
                  </div>
                  <div className='text-lg font-bold text-white'>
                    {statistics.avg_thumbnail_size_kb.toFixed(1)}KB
                  </div>
                </div>
              </div>

              <div className='text-xs text-grey-light/70 text-center'>
                Last updated:{" "}
                {new Date(statistics.last_updated).toLocaleString()}
              </div>
            </div>
          )}

          <Separator className='bg-purple-muted/20' />

          {/* Regeneration Status */}
          {regenerationStatus?.active && (
            <div className='space-y-4 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg'>
              <div className='flex items-center justify-between'>
                <div className='flex items-center space-x-2'>
                  <Loader2 className='w-4 h-4 text-blue-400 animate-spin' />
                  <span className='text-sm font-medium text-blue-300'>
                    Regenerating Thumbnails
                  </span>
                </div>
                <Button
                  onClick={cancelRegeneration}
                  variant='outline'
                  size='sm'
                  className='border-red-500/50 hover:bg-red-500/20 text-red-400'
                >
                  <X className='w-4 h-4 mr-2' />
                  Cancel
                </Button>
              </div>

              <div className='space-y-2'>
                <div className='flex items-center justify-between text-sm'>
                  <span className='text-grey-light/70'>
                    Progress: {regenerationStatus.completed_images}/
                    {regenerationStatus.total_images}
                  </span>
                  <span className='text-white font-medium'>
                    {regenerationStatus.progress}%
                  </span>
                </div>
                <Progress value={regenerationStatus.progress} className='h-2' />
                {regenerationStatus.estimated_time_remaining_seconds && (
                  <div className='text-xs text-grey-light/70'>
                    Est. time remaining:{" "}
                    {formatDuration(
                      regenerationStatus.estimated_time_remaining_seconds
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Management Actions */}
          <div className='space-y-4'>
            <div className='flex items-center space-x-2'>
              <Wrench className='w-4 h-4 text-pink' />
              <h4 className='text-sm font-medium text-white'>
                Management Operations
              </h4>
            </div>

            <div className='grid grid-cols-2 md:grid-cols-3 gap-4'>
              {/* Verify All Thumbnails */}
              <Button
                onClick={verifyAllThumbnails}
                disabled={!!operationInProgress}
                className='h-auto p-4 flex flex-col items-start space-y-2 bg-cyan/10 hover:bg-cyan/20 border border-cyan/20 text-cyan'
              >
                <div className='flex items-center space-x-2'>
                  <CheckCircle className='w-4 h-4' />
                  <span className='font-medium'>Verify All</span>
                </div>
                <span className='text-xs text-grey-light/70 text-left'>
                  Check file existence for all thumbnails system-wide
                </span>
                {operationInProgress === "verify" && (
                  <Loader2 className='w-4 h-4 animate-spin' />
                )}
              </Button>

              {/* Repair Orphaned */}
              <Button
                onClick={repairOrphanedThumbnails}
                disabled={!!operationInProgress}
                className='h-auto p-4 flex flex-col items-start space-y-2 bg-yellow/10 hover:bg-yellow/20 border border-yellow/20 text-yellow'
              >
                <div className='flex items-center space-x-2'>
                  <Wrench className='w-4 h-4' />
                  <span className='font-medium'>Repair Orphaned</span>
                </div>
                <span className='text-xs text-grey-light/70 text-left'>
                  Scan filesystem and match orphaned files to database
                </span>
                {operationInProgress === "repair" && (
                  <Loader2 className='w-4 h-4 animate-spin' />
                )}
              </Button>

              {/* Regenerate All */}
              <Button
                disabled={!!operationInProgress || regenerationStatus?.active}
                onClick={() => setShowRegenerationModal(true)}
                className='h-auto p-4 flex flex-col items-start space-y-2 bg-purple/10 hover:bg-purple/20 border border-purple/20 text-purple'
              >
                <div className='flex items-center space-x-2'>
                  <RefreshCw className='w-4 h-4' />
                  <span className='font-medium'>Regenerate All</span>
                </div>
                <p className='text-xs text-grey-light/70 text-left text-wrap'>
                  Force regenerate thumbnails for all images
                </p>
                {operationInProgress === "regenerate" && (
                  <Loader2 className='w-4 h-4 animate-spin' />
                )}
              </Button>

              {/* Cleanup Orphaned Files */}
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    disabled={!!operationInProgress}
                    className='h-auto p-4 flex flex-col items-start space-y-2 bg-orange-500/10 hover:bg-orange-500/20 border border-orange-500/20 text-orange-400'
                  >
                    <div className='flex items-center space-x-2'>
                      <Trash2 className='w-4 h-4' />
                      <span className='font-medium'>Cleanup Orphaned</span>
                    </div>
                    <span className='text-xs text-grey-light/70 text-left'>
                      Delete orphaned thumbnail files from filesystem
                    </span>
                    {operationInProgress === "cleanup" && (
                      <Loader2 className='w-4 h-4 animate-spin' />
                    )}
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent className='glass-strong border-purple-muted/50'>
                  <AlertDialogHeader>
                    <AlertDialogTitle className='flex items-center space-x-2'>
                      <AlertTriangle className='w-5 h-5 text-orange-400' />
                      <span>Cleanup Orphaned Files</span>
                    </AlertDialogTitle>
                    <AlertDialogDescription>
                      This will permanently delete thumbnail files that are not
                      referenced in the database. This action cannot be undone.
                    </AlertDialogDescription>
                    <div className='mt-3 p-3 bg-orange-500/10 border border-orange-500/20 rounded text-sm'>
                      <strong>Warning:</strong> Only orphaned files will be
                      deleted. Files with valid database references will be
                      preserved.
                    </div>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel className='border-purple-muted/40 hover:bg-purple-muted/20'>
                      Cancel
                    </AlertDialogCancel>
                    <AlertDialogAction
                      onClick={cleanupOrphanedFiles}
                      className='bg-orange-500/20 hover:bg-orange-500/30 text-orange-400 border-orange-500/30'
                    >
                      Delete Orphaned Files
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>

              {/* Delete All Thumbnails */}
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    disabled={!!operationInProgress}
                    className='h-auto p-4 flex flex-col items-start space-y-2 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400'
                  >
                    <div className='flex items-center space-x-2'>
                      <XCircle className='w-4 h-4' />
                      <span className='font-medium'>Delete All</span>
                    </div>
                    <span className='text-xs text-grey-light/70 text-left'>
                      Remove all thumbnail files and database references
                    </span>
                    {operationInProgress === "deleteAll" && (
                      <Loader2 className='w-4 h-4 animate-spin' />
                    )}
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent className='glass-strong border-purple-muted/50'>
                  <AlertDialogHeader>
                    <AlertDialogTitle className='flex items-center space-x-2'>
                      <AlertTriangle className='w-5 h-5 text-red-400' />
                      <span>Delete All Thumbnails</span>
                    </AlertDialogTitle>
                    <AlertDialogDescription>
                      This will permanently delete ALL thumbnail files and clear
                      all database references. This action cannot be undone.
                    </AlertDialogDescription>
                    {statistics && (
                      <div className='mt-3 p-3 bg-red-500/10 border border-red-500/20 rounded text-sm'>
                        <strong>Warning:</strong> This will delete{" "}
                        {(
                          statistics.images_with_thumbnails || 0
                        ).toLocaleString()}{" "}
                        thumbnails (
                        {formatFileSize(
                          (statistics.total_thumbnail_storage_mb || 0) +
                            (statistics.total_small_storage_mb || 0)
                        )}{" "}
                        of storage).
                      </div>
                    )}
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel className='border-purple-muted/40 hover:bg-purple-muted/20'>
                      Cancel
                    </AlertDialogCancel>
                    <AlertDialogAction
                      onClick={deleteAllThumbnails}
                      className='bg-red-500/20 hover:bg-red-500/30 text-red-400 border-red-500/30'
                    >
                      Delete All Thumbnails
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Results Dialog */}
      {showResults && (
        <AlertDialog
          open={!!showResults}
          onOpenChange={() => setShowResults(null)}
        >
          <AlertDialogContent className='glass-strong border-purple-muted/50 max-w-2xl'>
            <AlertDialogHeader>
              <AlertDialogTitle className='flex items-center space-x-2'>
                <CheckCircle className='w-5 h-5 text-success' />
                <span>{showResults.operation} Results</span>
              </AlertDialogTitle>
              <AlertDialogDescription className='text-left'>
                {showResults.result.message}

                {showResults.result.data && (
                  <>
                    <br />
                    <br />
                    <span className='text-sm'>
                      {Object.entries(showResults.result.data).map(
                        ([key, value], index) => (
                          <span key={key}>
                            <span className='text-grey-light/70 capitalize'>
                              {key.replace(/_/g, " ")}:
                            </span>
                            <span className='text-white font-medium'>
                              {typeof value === "number"
                                ? value.toLocaleString()
                                : String(value)}
                            </span>
                            {index <
                              Object.entries(showResults.result.data!).length -
                                1 && <br />}
                          </span>
                        )
                      )}
                    </span>
                  </>
                )}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogAction
                onClick={() => setShowResults(null)}
                className='bg-success/20 hover:bg-success/30 text-success border-success/30'
              >
                Close
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      )}

      {/* Thumbnail Regeneration Modal */}
      <ThumbnailRegenerationModal
        isOpen={showRegenerationModal}
        onClose={() => setShowRegenerationModal(false)}
      />
    </>
  )
}
