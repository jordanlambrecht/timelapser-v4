export interface SettingsState {
  // Core settings
  captureInterval: number
  timezone: string
  generateThumbnails: boolean
  imageCaptureType: "PNG" | "JPG"

  // API settings
  openWeatherApiKey: string
  apiKeyModified: boolean
  originalApiKeyHash: string

  // Logging settings
  logRetentionDays: number
  maxLogFileSize: number
  enableDebugLogging: boolean
  logLevel: string
  enableLogRotation: boolean
  enableLogCompression: boolean
  maxLogFiles: number

  // UI state
  loading: boolean
  saving: boolean
}

export interface SettingsActions {
  // Core settings
  setCaptureInterval: (value: number) => void
  setTimezone: (value: string) => void
  setGenerateThumbnails: (value: boolean) => void
  setImageCaptureType: (value: "PNG" | "JPG") => void

  // API settings
  setOpenWeatherApiKey: (value: string) => void
  setApiKeyModified: (value: boolean) => void
  setOriginalApiKeyHash: (value: string) => void

  // Logging settings
  setLogRetentionDays: (value: number) => void
  setMaxLogFileSize: (value: number) => void
  setEnableDebugLogging: (value: boolean) => void
  setLogLevel: (value: string) => void
  setEnableLogRotation: (value: boolean) => void
  setEnableLogCompression: (value: boolean) => void
  setMaxLogFiles: (value: number) => void

  // Actions
  fetchSettings: () => Promise<void>
  saveSettings: () => Promise<void>
}
