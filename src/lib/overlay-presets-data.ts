// src/lib/overlay-presets-data.ts

export interface OverlayPreset {
  id: number
  name: string
  description: string
  isBuiltin: boolean
  lastUsed: string | null
  overlayCount: number
  positions: string[]
}

export const MOCK_OVERLAY_PRESETS: OverlayPreset[] = [
  {
    id: 1,
    name: "Basic Timestamp",
    description: "Simple date and time overlay in bottom-left corner",
    isBuiltin: true,
    lastUsed: "2025-01-08",
    overlayCount: 2,
    positions: ["bottomLeft", "topRight"],
  },
  {
    id: 2,
    name: "Weather + Time",
    description: "Weather conditions with timestamp and temperature",
    isBuiltin: true,
    lastUsed: "2025-01-07",
    overlayCount: 3,
    positions: ["topLeft", "topRight", "bottomLeft"],
  },
  {
    id: 3,
    name: "Minimal",
    description: "Just frame count in corner",
    isBuiltin: true,
    lastUsed: null,
    overlayCount: 1,
    positions: ["bottomRight"],
  },
  {
    id: 4,
    name: "Full Info Dashboard",
    description: "Complete information overlay with custom watermark",
    isBuiltin: false,
    lastUsed: "2025-01-09",
    overlayCount: 5,
    positions: [
      "topLeft",
      "topCenter",
      "topRight",
      "bottomLeft",
      "bottomRight",
    ],
  },
  {
    id: 5,
    name: "Clean Branding",
    description: "Company logo with minimal text",
    isBuiltin: false,
    lastUsed: "2025-01-06",
    overlayCount: 2,
    positions: ["topRight", "bottomRight"],
  },
]

export const OVERLAY_TYPES = [
  {
    value: "date_time",
    label: "Date & Time",
    description: "Customizable date and time format",
  },
  {
    value: "frame_number",
    label: "Frame Number",
    description: "Current frame count",
  },
  { value: "day_number", label: "Day Number", description: "Days since start" },
  {
    value: "timelapse_name",
    label: "Timelapse Name",
    description: "Name of timelapse",
  },
  {
    value: "custom_text",
    label: "Custom Text",
    description: "Static custom text",
  },
  {
    value: "temperature",
    label: "Temperature",
    description: "Current temperature",
  },
  {
    value: "weather_conditions",
    label: "Weather",
    description: "Weather description",
  },
  {
    value: "weather",
    label: "Weather + Temp",
    description: "Combined weather info",
  },
  { value: "watermark", label: "Watermark/Logo", description: "Image overlay" },
] as const

export type OverlayType = (typeof OVERLAY_TYPES)[number]["value"]

export const GRID_POSITIONS = [
  "topLeft",
  "topCenter",
  "topRight",
  "centerLeft",
  "center",
  "centerRight",
  "bottomLeft",
  "bottomCenter",
  "bottomRight",
] as const

export type GridPosition = (typeof GRID_POSITIONS)[number]

export const POSITION_LABELS: Record<GridPosition, string> = {
  topLeft: "Top Left",
  topCenter: "Top Center",
  topRight: "Top Right",
  centerLeft: "Center Left",
  center: "Center",
  centerRight: "Center Right",
  bottomLeft: "Bottom Left",
  bottomCenter: "Bottom Center",
  bottomRight: "Bottom Right",
}
