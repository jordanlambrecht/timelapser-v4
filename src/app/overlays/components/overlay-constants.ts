// src/app/overlays/components/overlay-constants.ts

import {
  Camera,
  DownloadCloud,
  Cloud,
  Hash,
  Calendar,
  Type,
  FileText,
  Activity,
  Image as ImageIcon,
} from "lucide-react"

// Grid positions mapping
export const GRID_POSITIONS = [
  { id: "topLeft", row: 0, col: 0, label: "Top Left" },
  { id: "topCenter", row: 0, col: 1, label: "Top Center" },
  { id: "topRight", row: 0, col: 2, label: "Top Right" },
  { id: "centerLeft", row: 1, col: 0, label: "Center Left" },
  { id: "center", row: 1, col: 1, label: "Center" },
  { id: "centerRight", row: 1, col: 2, label: "Center Right" },
  { id: "bottomLeft", row: 2, col: 0, label: "Bottom Left" },
  { id: "bottomCenter", row: 2, col: 1, label: "Bottom Center" },
  { id: "bottomRight", row: 2, col: 2, label: "Bottom Right" },
] as const

export const OVERLAY_TYPES = [
  {
    id: "weather",
    label: "Weather",
    icon: Cloud,
    description: "Temperature and conditions",
  },
  {
    id: "date_time",
    label: "Date & Time",
    icon: Calendar,
    description: "Current date and time",
  },
  {
    id: "frame_number",
    label: "Frame Number",
    icon: Hash,
    description: "Image sequence number",
  },
  {
    id: "custom_text",
    label: "Custom Text",
    icon: Type,
    description: "Custom text overlay",
  },
  {
    id: "timelapse_name",
    label: "Timelapse Name",
    icon: FileText,
    description: "Project name",
  },
  {
    id: "day_number",
    label: "Day Counter",
    icon: Activity,
    description: "Days since start",
  },
  {
    id: "watermark",
    label: "Image Watermark",
    icon: ImageIcon,
    description: "Custom image overlay",
  },
] as const

// Default settings for different overlay types
export const getDefaultSettings = (type: string) => {
  switch (type) {
    case "weather":
      return {
        unit: "Celsius",
        display: "both",
        textSize: 16,
        enableBackground: true,
      }
    case "watermark":
      return { imageScale: 100, imageUrl: "" }
    case "frame_number":
      return { textSize: 16, leadingZeros: false, enableBackground: false }
    case "date_time":
      return {
        dateFormat: "YYYY-MM-DD HH:mm",
        textSize: 16,
        enableBackground: false,
      }
    case "day_number":
      return {
        leadingZeros: false,
        textSize: 16,
        hidePrefix: false,
        enableBackground: false,
      }
    case "custom_text":
      return {
        customText: "Custom Text",
        textSize: 16,
        enableBackground: false,
      }
    case "timelapse_name":
      return { textSize: 16, enableBackground: false }
    default:
      return {}
  }
}

// Position styling helper
export const getPositionStyles = (position: string) => {
  switch (position) {
    case "topLeft":
      return "top-4 left-4"
    case "topCenter":
      return "top-4 left-1/2 transform -translate-x-1/2"
    case "topRight":
      return "top-4 right-4"
    case "centerLeft":
      return "top-1/2 left-4 transform -translate-y-1/2"
    case "center":
      return "top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2"
    case "centerRight":
      return "top-1/2 right-4 transform -translate-y-1/2"
    case "bottomLeft":
      return "bottom-4 left-4"
    case "bottomCenter":
      return "bottom-4 left-1/2 transform -translate-x-1/2"
    case "bottomRight":
      return "bottom-4 right-4"
    default:
      return "top-4 left-4"
  }
}
