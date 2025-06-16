import { toast as sonnerToast } from "sonner"

interface ToastOptions {
  description?: string
  duration?: number
  action?: {
    label: string
    onClick: () => void
  }
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
}

export default toast
