import { toast as sonnerToast } from "sonner"

interface ToastOptions {
  description?: string
  duration?: number
  action?: {
    label: string
    onClick: () => void | Promise<void>
  }
}

interface UndoToastOptions extends ToastOptions {
  undoAction: () => void | Promise<void>
  undoLabel?: string
  undoTimeout?: number
}

const defaultOptions = {
  duration: 4000,
  richColors: true,
}

/**
 * Centralized toast utility using Sonner with brand-consistent styling
 * Uses the brand color palette defined in globals.css
 */
export const toast = {
  /**
   * Show a success toast (green)
   */
  success: (message: string, options: ToastOptions = {}) => {
    return sonnerToast.success(message, {
      ...defaultOptions,
      ...options,
      style: {
        backgroundColor: "oklch(80% 0.182 152deg / 0.1)",
        borderColor: "oklch(80% 0.182 152deg / 0.3)",
        color: "oklch(80% 0.182 152deg)",
      },
    })
  },

  /**
   * Show an error toast (red/orange)
   */
  error: (message: string, options: ToastOptions = {}) => {
    return sonnerToast.error(message, {
      ...defaultOptions,
      duration: 6000, // Longer duration for errors
      ...options,
      style: {
        backgroundColor: "oklch(66.8% 0.22 19.6deg / 0.1)",
        borderColor: "oklch(66.8% 0.22 19.6deg / 0.3)",
        color: "oklch(66.8% 0.22 19.6deg)",
      },
    })
  },

  /**
   * Show a warning toast (yellow)
   */
  warning: (message: string, options: ToastOptions = {}) => {
    return sonnerToast.warning(message, {
      ...defaultOptions,
      ...options,
      style: {
        backgroundColor: "oklch(84.2% 0.128 71.8deg / 0.1)",
        borderColor: "oklch(84.2% 0.128 71.8deg / 0.3)",
        color: "oklch(84.2% 0.128 71.8deg)",
      },
    })
  },

  /**
   * Show an info toast (pink - brand primary)
   */
  info: (message: string, options: ToastOptions = {}) => {
    return sonnerToast.info(message, {
      ...defaultOptions,
      ...options,
      style: {
        backgroundColor: "oklch(91.1% 0.046 18deg / 0.1)",
        borderColor: "oklch(91.1% 0.046 18deg / 0.3)",
        color: "oklch(91.1% 0.046 18deg)",
      },
    })
  },

  /**
   * Show a custom toast with brand styling
   */
  custom: (message: string, options: ToastOptions = {}) => {
    return sonnerToast(message, {
      ...defaultOptions,
      ...options,
      style: {
        backgroundColor: "oklch(23.4% 0.0065 258deg / 0.8)",
        borderColor: "oklch(46.1% 0.0708 275deg / 0.3)",
        color: "oklch(99.1% 0.00426 17.2deg)",
      },
    })
  },

  /**
   * Show a loading toast
   */
  loading: (message: string, options: Omit<ToastOptions, "duration"> = {}) => {
    return sonnerToast.loading(message, {
      ...defaultOptions,
      duration: Infinity, // Loading toasts don't auto-dismiss
      ...options,
      style: {
        backgroundColor: "oklch(51.2% 0.242 280deg / 0.1)",
        borderColor: "oklch(51.2% 0.242 280deg / 0.3)",
        color: "oklch(51.2% 0.242 280deg)",
      },
    })
  },

  /**
   * Dismiss a specific toast by ID
   */
  dismiss: (toastId?: string | number) => {
    return sonnerToast.dismiss(toastId)
  },

  /**
   * Dismiss all toasts
   */
  dismissAll: () => {
    return sonnerToast.dismiss()
  },

  // Specialized toast functions for common use cases

  /**
   * Show a success toast with undo action
   */
  successWithUndo: (message: string, options: UndoToastOptions) => {
    const {
      undoAction,
      undoLabel = "Undo",
      undoTimeout = 5000,
      ...restOptions
    } = options

    return sonnerToast.success(message, {
      ...defaultOptions,
      duration: undoTimeout,
      ...restOptions,
      action: {
        label: undoLabel,
        onClick: async () => {
          try {
            await undoAction()
          } catch (error) {
            console.error("Undo action failed:", error)
            toast.error("Undo failed", {
              description: "Please try the operation again",
              duration: 4000,
            })
          }
        },
      },
      style: {
        backgroundColor: "oklch(80% 0.182 152deg / 0.1)",
        borderColor: "oklch(80% 0.182 152deg / 0.3)",
        color: "oklch(80% 0.182 152deg)",
      },
    })
  },

  // Specific application toasts

  /**
   * Toast for when an image is captured
   */
  imageCaptured: (cameraName: string, options: ToastOptions = {}) => {
    return toast.success(`📸 Image captured from ${cameraName}`, {
      description: "New image added to timelapse sequence",
      duration: 3000,
      ...options,
    })
  },

  /**
   * Toast for when a camera is deleted (with undo)
   */
  cameraDeleted: (
    cameraName: string,
    undoAction: () => void | Promise<void>
  ) => {
    return toast.successWithUndo(`Camera "${cameraName}" deleted`, {
      description: "Camera and all its data have been removed",
      undoAction,
      undoTimeout: 8000,
    })
  },

  /**
   * Toast for when a timelapse video is deleted (with undo)
   */
  timelapseDeleted: (
    videoName: string,
    undoAction: () => void | Promise<void>
  ) => {
    return toast.successWithUndo(`Timelapse "${videoName}" deleted`, {
      description: "Video file has been removed",
      undoAction,
      undoTimeout: 8000,
    })
  },

  /**
   * Toast for when a camera is renamed
   */
  cameraRenamed: (
    oldName: string,
    newName: string,
    options: ToastOptions = {}
  ) => {
    return toast.success(`Camera renamed to "${newName}"`, {
      description: `Previously known as "${oldName}"`,
      duration: 4000,
      ...options,
    })
  },

  /**
   * Toast for when a timelapse is paused
   */
  timelapsePaused: (cameraName: string, options: ToastOptions = {}) => {
    return toast.info(`⏸️ Timelapse paused for ${cameraName}`, {
      description: "Recording will resume when you unpause",
      duration: 4000,
      ...options,
    })
  },

  /**
   * Toast for when a timelapse is resumed
   */
  timelapseResumed: (cameraName: string, options: ToastOptions = {}) => {
    return toast.success(`▶️ Timelapse resumed for ${cameraName}`, {
      description: "Recording has continued from where it left off",
      duration: 4000,
      ...options,
    })
  },

  /**
   * Toast for when a timelapse is stopped (with undo)
   */
  timelapseStopped: (
    cameraName: string,
    undoAction: () => void | Promise<void>
  ) => {
    return toast.successWithUndo(`⏹️ Timelapse stopped for ${cameraName}`, {
      description: "Recording session has ended",
      undoAction,
      undoLabel: "Restart",
      undoTimeout: 8000,
    })
  },

  /**
   * Toast for when a camera is added
   */
  cameraAdded: (cameraName: string, options: ToastOptions = {}) => {
    return toast.success(`📹 Camera "${cameraName}" added successfully`, {
      description: "Camera is now ready for timelapse recording",
      duration: 5000,
      ...options,
    })
  },

  /**
   * Toast for when a timelapse video is renamed
   */
  timelapseRenamed: (
    oldName: string,
    newName: string,
    options: ToastOptions = {}
  ) => {
    return toast.success(`Video renamed to "${newName}"`, {
      description: `Previously known as "${oldName}"`,
      duration: 4000,
      ...options,
    })
  },

  /**
   * Toast for when a timelapse is started
   */
  timelapseStarted: (cameraName: string, options: ToastOptions = {}) => {
    return toast.success(`🎬 Timelapse started for ${cameraName}`, {
      description:
        "Recording has begun - images will be captured automatically",
      duration: 5000,
      ...options,
    })
  },

  /**
   * Toast for video generation progress
   */
  videoGenerating: (videoName: string, options: ToastOptions = {}) => {
    return toast.loading(`🎬 Generating video "${videoName}"...`, {
      description:
        "This may take a few minutes depending on the number of images",
      ...options,
    })
  },

  /**
   * Toast for successful video generation
   */
  videoGenerated: (videoName: string, options: ToastOptions = {}) => {
    return toast.success(`🎉 Video "${videoName}" generated successfully!`, {
      description: "Your timelapse video is ready for download",
      duration: 6000,
      ...options,
    })
  },
}

export default toast
