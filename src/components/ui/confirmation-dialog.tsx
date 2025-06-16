import { ReactNode, useState } from "react"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Trash2, StopCircle, AlertTriangle, Loader2 } from "lucide-react"

interface ConfirmationDialogProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void | Promise<void>
  title: string
  description: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: "danger" | "warning" | "default"
  icon?: ReactNode
  isLoading?: boolean
}

export function ConfirmationDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "default",
  icon,
  isLoading = false,
}: ConfirmationDialogProps) {
  const [internalLoading, setInternalLoading] = useState(false)

  const handleConfirm = async () => {
    setInternalLoading(true)
    try {
      await onConfirm()
      if (!isLoading) {
        onClose()
      }
    } catch (error) {
      console.error("Confirmation action failed:", error)
    } finally {
      setInternalLoading(false)
    }
  }

  const getVariantStyles = () => {
    switch (variant) {
      case "danger":
        return {
          iconColor: "text-failure",
          confirmClass: "bg-failure hover:bg-failure/90 text-white font-bold",
          borderClass: "border-failure/20",
          bgClass: "from-failure/5 to-transparent",
        }
      case "warning":
        return {
          iconColor: "text-yellow",
          confirmClass: "bg-yellow hover:bg-yellow/90 text-black font-bold",
          borderClass: "border-yellow/20",
          bgClass: "from-yellow/5 to-transparent",
        }
      default:
        return {
          iconColor: "text-cyan",
          confirmClass: "bg-gradient-to-r from-pink to-cyan hover:from-pink-dark hover:to-cyan text-black font-bold",
          borderClass: "border-purple-muted/20",
          bgClass: "from-cyan/5 to-transparent",
        }
    }
  }

  const styles = getVariantStyles()
  const loading = isLoading || internalLoading

  return (
    <AlertDialog open={isOpen} onOpenChange={onClose}>
      <AlertDialogContent className={`glass-strong border-purple-muted/50 max-w-md ${styles.borderClass}`}>
        <AlertDialogHeader className="relative">
          <div className={`absolute -top-2 -right-2 w-16 h-16 bg-gradient-to-bl ${styles.bgClass} rounded-full`} />
          <AlertDialogTitle className="flex items-center space-x-3 text-xl">
            <div className={`p-2 bg-gradient-to-br from-purple/20 to-cyan/20 rounded-xl ${styles.iconColor}`}>
              {icon || <AlertTriangle className="w-6 h-6" />}
            </div>
            <span className="text-white">{title}</span>
          </AlertDialogTitle>
          <AlertDialogDescription className="text-grey-light/80 text-base mt-4">
            {description}
          </AlertDialogDescription>
        </AlertDialogHeader>

        <AlertDialogFooter className="gap-3 pt-4">
          <AlertDialogCancel
            className="px-6 border-purple-muted/40 hover:bg-purple-muted/20 text-grey-light hover:text-white"
            disabled={loading}
          >
            {cancelLabel}
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={loading}
            className={`px-8 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed ${styles.confirmClass}`}
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Processing...
              </>
            ) : (
              confirmLabel
            )}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

// Specialized confirmation dialogs for common use cases
export function DeleteCameraConfirmationDialog({
  isOpen,
  onClose,
  onConfirm,
  cameraName,
  isLoading = false,
}: {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void | Promise<void>
  cameraName: string
  isLoading?: boolean
}) {
  return (
    <ConfirmationDialog
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      title="Delete Camera"
      description={`Are you sure you want to delete "${cameraName}"? This will permanently remove the camera and all its captured images. This action cannot be undone.`}
      confirmLabel="Delete Camera"
      cancelLabel="Keep Camera"
      variant="danger"
      icon={<Trash2 className="w-6 h-6" />}
      isLoading={isLoading}
    />
  )
}

export function DeleteTimelapseConfirmationDialog({
  isOpen,
  onClose,
  onConfirm,
  timelapseVideoName,
  isLoading = false,
}: {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void | Promise<void>
  timelapseVideoName: string
  isLoading?: boolean
}) {
  return (
    <ConfirmationDialog
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      title="Delete Timelapse Video"
      description={`Are you sure you want to delete "${timelapseVideoName}"? This will permanently remove the video file. This action cannot be undone.`}
      confirmLabel="Delete Video"
      cancelLabel="Keep Video"
      variant="danger"
      icon={<Trash2 className="w-6 h-6" />}
      isLoading={isLoading}
    />
  )
}

export function StopTimelapseConfirmationDialog({
  isOpen,
  onClose,
  onConfirm,
  cameraName,
  isLoading = false,
}: {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void | Promise<void>
  cameraName: string
  isLoading?: boolean
}) {
  return (
    <ConfirmationDialog
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      title="Stop Timelapse"
      description={`Are you sure you want to stop the timelapse for "${cameraName}"? This will end the current recording session. You can restart it later, but the current session will be completed.`}
      confirmLabel="Stop Timelapse"
      cancelLabel="Continue Recording"
      variant="warning"
      icon={<StopCircle className="w-6 h-6" />}
      isLoading={isLoading}
    />
  )
}

export function StopAllTimelapsesConfirmationDialog({
  isOpen,
  onClose,
  onConfirm,
  cameraCount,
  isLoading = false,
}: {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void | Promise<void>
  cameraCount: number
  isLoading?: boolean
}) {
  return (
    <ConfirmationDialog
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      title="Stop All Timelapses"
      description={`Are you sure you want to stop all active timelapses? This will end all current recording sessions across ${cameraCount} camera${cameraCount !== 1 ? 's' : ''}. You can restart them later, but the current sessions will be completed.`}
      confirmLabel="Stop All Timelapses"
      cancelLabel="Keep Recording"
      variant="warning"
      icon={<StopCircle className="w-6 h-6" />}
      isLoading={isLoading}
    />
  )
}
