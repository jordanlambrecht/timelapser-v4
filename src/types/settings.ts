import { ReactNode } from "react"

export interface SettingsState {
  // Core settings
  timezone: string
  enableThumbnailGeneration: boolean
  smallGenerationMode: boolean
  purgeSmalllsOnCompletion: boolean
  imageCaptureType: "PNG" | "JPG"

  // API settings
  openWeatherApiKey: string
  apiKeyModified: boolean
  originalApiKeyHash: string

  // Weather settings
  weatherIntegrationEnabled: boolean
  weatherRecordData: boolean
  sunriseSunsetEnabled: boolean
  latitude: number | null
  longitude: number | null

  // Logging settings
  logRetentionDays: number
  maxLogFileSize: number
  enableDebugLogging: boolean
  logLevel: string
  enableLogRotation: boolean
  enableLogCompression: boolean
  maxLogFiles: number

  // Corruption detection settings
  corruptionDetectionEnabled: boolean
  corruptionScoreThreshold: number
  corruptionAutoDiscardEnabled: boolean
  corruptionAutoDisableDegraded: boolean
  corruptionDegradedConsecutiveThreshold: number
  corruptionDegradedTimeWindowMinutes: number
  corruptionDegradedFailurePercentage: number
  corruptionHeavyDetectionEnabled: boolean

  // UI state
  loading: boolean
  saving: boolean
}

export interface SettingsActions {
  // Core settings
  setTimezone: (value: string) => void
  setEnableThumbnailGeneration: (value: boolean) => void
  setSmallGenerationMode: (value: boolean) => void
  setPurgeSmallsOnCompletion: (value: boolean) => void
  setImageCaptureType: (value: "PNG" | "JPG") => void

  // API settings
  setOpenWeatherApiKey: (value: string) => void
  setApiKeyModified: (value: boolean) => void
  setOriginalApiKeyHash: (value: string) => void

  // Weather settings
  setWeatherIntegrationEnabled: (value: boolean) => void
  setWeatherRecordData: (value: boolean) => void
  setSunriseSunsetEnabled: (value: boolean) => void
  setLatitude: (value: number | null) => void
  setLongitude: (value: number | null) => void

  // Logging settings
  setLogRetentionDays: (value: number) => void
  setMaxLogFileSize: (value: number) => void
  setEnableDebugLogging: (value: boolean) => void
  setLogLevel: (value: string) => void
  setEnableLogRotation: (value: boolean) => void
  setEnableLogCompression: (value: boolean) => void
  setMaxLogFiles: (value: number) => void

  // Corruption detection settings
  setCorruptionDetectionEnabled: (value: boolean) => void
  setCorruptionScoreThreshold: (value: number) => void
  setCorruptionAutoDiscardEnabled: (value: boolean) => void
  setCorruptionAutoDisableDegraded: (value: boolean) => void
  setCorruptionDegradedConsecutiveThreshold: (value: number) => void
  setCorruptionDegradedTimeWindowMinutes: (value: number) => void
  setCorruptionDegradedFailurePercentage: (value: number) => void
  setCorruptionHeavyDetectionEnabled: (value: boolean) => void

  // Actions
  fetchSettings: () => Promise<void>
  saveSettings: () => Promise<void>
}

// Settings Component Props
export interface ApiKeySettingsCardProps {
  openWeatherApiKey: string
  setOpenWeatherApiKey: (value: string) => void
  apiKeyModified: boolean
  setApiKeyModified: (value: boolean) => void
  originalApiKeyHash: string
}

export interface CaptureSettingsCardProps {
  enableThumbnailGeneration: boolean
  setEnableThumbnailGeneration: (value: boolean) => void
  smallGenerationMode: boolean
  setSmallGenerationMode: (value: boolean) => void
  purgeSmalllsOnCompletion: boolean
  setPurgeSmallsOnCompletion: (value: boolean) => void
  imageCaptureType: "PNG" | "JPG"
  setImageCaptureType: (value: "PNG" | "JPG") => void
  saving: boolean
}

export interface CorruptionSettingsCardProps {
  // Global settings
  corruptionDetectionEnabled: boolean
  setCorruptionDetectionEnabled: (value: boolean) => void
  corruptionScoreThreshold: number
  setCorruptionScoreThreshold: (value: number) => void
  corruptionAutoDiscardEnabled: boolean
  setCorruptionAutoDiscardEnabled: (value: boolean) => void
  corruptionAutoDisableDegraded: boolean
  setCorruptionAutoDisableDegraded: (value: boolean) => void
  corruptionDegradedConsecutiveThreshold: number
  setCorruptionDegradedConsecutiveThreshold: (value: number) => void
  corruptionDegradedTimeWindowMinutes: number
  setCorruptionDegradedTimeWindowMinutes: (value: number) => void
  corruptionDegradedFailurePercentage: number
  setCorruptionDegradedFailurePercentage: (value: number) => void
  corruptionHeavyDetectionEnabled: boolean
  setCorruptionHeavyDetectionEnabled: (value: boolean) => void
}

export interface CurrentConfigurationCardProps {
  settings: SettingsState
}

export interface LoggingSettingsCardProps {
  logRetentionDays: number
  setLogRetentionDays: (value: number) => void
  maxLogFileSize: number
  setMaxLogFileSize: (value: number) => void
  enableDebugLogging: boolean
  setEnableDebugLogging: (value: boolean) => void
  logLevel: string
  setLogLevel: (value: string) => void
  enableLogRotation: boolean
  setEnableLogRotation: (value: boolean) => void
  enableLogCompression: boolean
  setEnableLogCompression: (value: boolean) => void
  maxLogFiles: number
  setMaxLogFiles: (value: number) => void
}

export interface SettingsProviderProps {
  children: ReactNode
}

export interface TimezoneSettingsCardProps {
  timezone: string
  onTimezoneChange: (value: string) => void
  saving: boolean
}

export interface WeatherSettingsCardProps {
  weatherIntegrationEnabled: boolean
  setWeatherIntegrationEnabled: (value: boolean) => void
  weatherRecordData: boolean
  setWeatherRecordData: (value: boolean) => void
  sunriseSunsetEnabled: boolean
  setSunriseSunsetEnabled: (value: boolean) => void
  latitude: number | null
  setLatitude: (value: number | null) => void
  longitude: number | null
  setLongitude: (value: number | null) => void
  openWeatherApiKey: string
  apiKeyModified: boolean
  originalApiKeyHash: string
}
