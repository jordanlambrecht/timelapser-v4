import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import {
  AlertCircle,
  CheckCircle2,
  Image as ImageIcon,
  Loader2,
  X,
  Zap,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useEffect, useState } from "react"
import { useSSESubscription } from "@/contexts/sse-context"
import { toast } from "@/lib/toast"

interface ThumbnailRegenerationModalProps {
  isOpen: boolean
  onClose: () => void
}

interface RegenerationProgress {
  active: boolean
  progress: number
  total: number
  current_image: string
  completed: number
  errors: number
}

export function ThumbnailRegenerationModal({
  isOpen,
  onClose,
}: ThumbnailRegenerationModalProps) {
  const [progress, setProgress] = useState<RegenerationProgress>({
    active: false,
    progress: 0,
    total: 0,
    current_image: "",
    completed: 0,
    errors: 0,
  })
  const [isStarting, setIsStarting] = useState(false)
  const [isCancelling, setIsCancelling] = useState(false)
  const [isComplete, setIsComplete] = useState(false)

  // SSE for real-time updates using centralized system
  useSSESubscription(
    (event) => event.type === "thumbnail_regeneration_progress",
    (event) => {
      setProgress({
        active: true,
        progress: event.progress,
        total: event.total,
        current_image: event.current_image,
        completed: event.completed,
        errors: event.errors,
      })
      setIsStarting(false)
    },
    [isOpen]
  )

  useSSESubscription(
    (event) => event.type === "thumbnail_regeneration_complete",
    (event) => {
      setProgress((prev) => ({
        ...prev,
        active: false,
      }))
      setIsComplete(true)
      setIsStarting(false)
      setIsCancelling(false)
      
      toast.success("Thumbnail regeneration completed!", {
        description: `Successfully processed ${event.completed}/${event.total} images`,
        duration: 5000,
      })
    },
    [isOpen]
  )

  useSSESubscription(
    (event) => event.type === "thumbnail_regeneration_cancelled",
    () => {
      setProgress((prev) => ({
        ...prev,
        active: false,
      }))
      setIsCancelling(false)
      toast.info("Thumbnail regeneration cancelled")
    },
    [isOpen]
  )

  useSSESubscription(
    (event) => event.type === "thumbnail_regeneration_error",
    (event) => {
      setProgress((prev) => ({
        ...prev,
        active: false,
      }))
      setIsStarting(false)
      setIsCancelling(false)
      toast.error("Thumbnail regeneration failed", {
        description: event.error,
        duration: 7000,
      })
    },
    [isOpen]
  )

  // Fetch initial status when modal opens
  useEffect(() => {
    if (isOpen) {
      fetchStatus()
    }
  }, [isOpen])

  const fetchStatus = async () => {
    try {
      const response = await fetch("/api/thumbnails/regenerate-all/status")
      if (response.ok) {
        const status = await response.json()
        setProgress(status)
        if (status.active) {
          setIsStarting(false)
        }
      }
    } catch (error) {
      console.error("Failed to fetch regeneration status:", error)
    }
  }

  const startRegeneration = async () => {
    setIsStarting(true)
    setIsComplete(false)

    try {
      const response = await fetch("/api/thumbnails/regenerate-all", {
        method: "POST",
      })

      if (response.ok) {
        toast.success("Thumbnail regeneration started", {
          description: "Processing will begin shortly...",
          duration: 3000,
        })
      } else {
        const error = await response.json()
        throw new Error(error.detail || "Failed to start regeneration")
      }
    } catch (error) {
      console.error("Error starting thumbnail regeneration:", error)
      setIsStarting(false)
      toast.error("Failed to start thumbnail regeneration", {
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        duration: 5000,
      })
    }
  }

  const cancelRegeneration = async () => {
    setIsCancelling(true)

    try {
      // If we're just starting but not active yet, just reset local state
      if (isStarting && !progress.active) {
        setIsStarting(false)
        setIsCancelling(false)
        toast.info("Startup cancelled")
        return
      }

      // Otherwise, call the backend cancel endpoint
      const response = await fetch("/api/thumbnails/regenerate-all/cancel", {
        method: "POST",
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || "Failed to cancel regeneration")
      }
    } catch (error) {
      console.error("Error cancelling thumbnail regeneration:", error)
      setIsCancelling(false)
      toast.error("Failed to cancel regeneration", {
        description:
          error instanceof Error ? error.message : "Unknown error occurred",
        duration: 5000,
      })
    }
  }

  const handleClose = () => {
    if (progress.active || isStarting) {
      // Don't allow closing while active or starting
      return
    }
    
    // Reset state when closing
    setProgress({
      active: false,
      progress: 0,
      total: 0,
      current_image: "",
      completed: 0,
      errors: 0,
    })
    setIsComplete(false)
    setIsStarting(false)
    setIsCancelling(false)
    onClose()
  }

  const progressPercentage = progress.total > 0 ? (progress.progress / progress.total) * 100 : 0

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-lg glass border-purple-muted">
        <DialogHeader>
          <DialogTitle className="flex items-center space-x-2">
            <div className="p-2 rounded-lg bg-gradient-to-br from-cyan/20 to-purple/20">
              <ImageIcon className="w-5 h-5 text-cyan" />
            </div>
            <span className="text-white">Regenerate All Thumbnails</span>
          </DialogTitle>
          <DialogDescription>
            Generate thumbnails and small images for all existing captures
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Progress Section */}
          {(progress.active || isStarting || isComplete) && (
            <div className="space-y-4">
              {/* Progress Bar */}
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-white">
                    {isStarting 
                      ? "Starting..."
                      : isComplete
                      ? "Completed"
                      : `Processing: ${progress.progress} / ${progress.total}`}
                  </span>
                  <span className="text-cyan">
                    {isStarting ? "0%" : `${Math.round(progressPercentage)}%`}
                  </span>
                </div>
                <Progress 
                  value={isStarting ? 0 : progressPercentage} 
                  className="h-3"
                />
              </div>

              {/* Current Status */}
              {progress.active && (
                <div className="p-4 rounded-lg bg-black/20 border border-purple-muted/30">
                  <div className="flex items-center space-x-3">
                    <Loader2 className="w-4 h-4 text-cyan animate-spin" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-white">
                        Currently Processing
                      </p>
                      <p className="text-xs text-gray-400 truncate">
                        {progress.current_image}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Stats */}
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-3 rounded-lg bg-green-500/10 border border-green-500/20">
                  <div className="flex items-center justify-center space-x-1 mb-1">
                    <CheckCircle2 className="w-4 h-4 text-green-400" />
                    <span className="text-sm font-medium text-green-400">Completed</span>
                  </div>
                  <div className="text-lg font-bold text-white">{progress.completed}</div>
                </div>

                <div className="text-center p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <div className="flex items-center justify-center space-x-1 mb-1">
                    <AlertCircle className="w-4 h-4 text-red-400" />
                    <span className="text-sm font-medium text-red-400">Errors</span>
                  </div>
                  <div className="text-lg font-bold text-white">{progress.errors}</div>
                </div>

                <div className="text-center p-3 rounded-lg bg-cyan-500/10 border border-cyan-500/20">
                  <div className="flex items-center justify-center space-x-1 mb-1">
                    <Zap className="w-4 h-4 text-cyan-400" />
                    <span className="text-sm font-medium text-cyan-400">Total</span>
                  </div>
                  <div className="text-lg font-bold text-white">{progress.total}</div>
                </div>
              </div>

              {/* Success Message */}
              {isComplete && (
                <div className="p-4 rounded-lg bg-green-500/10 border border-green-500/30">
                  <div className="flex items-center space-x-3">
                    <CheckCircle2 className="w-5 h-5 text-green-400" />
                    <div>
                      <p className="text-sm font-medium text-green-400">
                        Regeneration Complete!
                      </p>
                      <p className="text-xs text-gray-400">
                        Successfully processed {progress.completed} images with {progress.errors} errors
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Start/Idle State */}
          {!progress.active && !isStarting && !isComplete && (
            <div className="text-center space-y-4">
              <div className="p-6 rounded-lg bg-gradient-to-br from-cyan/5 to-purple/5 border border-purple-muted/30">
                <ImageIcon className="w-12 h-12 text-cyan mx-auto mb-3" />
                <p className="text-white font-medium mb-2">Ready to Generate Thumbnails</p>
                <p className="text-sm text-gray-400">
                  This will scan all existing images and create thumbnails for faster loading.
                  The process may take several minutes depending on the number of images.
                </p>
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex justify-end space-x-3">
            {(progress.active || isStarting) ? (
              <>
                <Button
                  variant="outline"
                  onClick={cancelRegeneration}
                  disabled={isCancelling}
                  className="border-red-500/50 text-red-400 hover:bg-red-500/10"
                >
                  {isCancelling ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Cancelling...
                    </>
                  ) : (
                    <>
                      <X className="w-4 h-4 mr-2" />
                      Cancel
                    </>
                  )}
                </Button>
              </>
            ) : (
              <>
                <Button
                  variant="outline"
                  onClick={handleClose}
                  disabled={false}
                  className="border-gray-600 text-white hover:bg-gray-700"
                >
                  {isComplete ? "Close" : "Cancel"}
                </Button>
                
                {!isComplete && (
                  <Button
                    onClick={startRegeneration}
                    disabled={false}
                    className="bg-gradient-to-r from-cyan to-purple text-black font-medium hover:shadow-lg"
                  >
                    <Zap className="w-4 h-4 mr-2" />
                    Start Regeneration
                  </Button>
                )}
              </>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}