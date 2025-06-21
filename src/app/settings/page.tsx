// src/app/settings/page.tsx
"use client"

import { Button } from "@/components/ui/button"
import { Save, RefreshCw } from "lucide-react"
import { useSettings } from "./hooks/use-settings"
import { DangerZoneCard } from "./components/danger-zone-card"
import { TimezoneSettingsCard } from "./components/timezone-settings-card"
import { LoggingSettingsCard } from "./components/logging-settings-card"
import { ApiKeySettingsCard } from "./components/api-key-settings-card"
import { CaptureSettingsCard } from "./components/capture-settings-card"
import { CorruptionSettingsCard } from "./components/corruption-settings-card"
import { WeatherSettingsCard } from "./components/weather-settings-card"
import { CurrentConfigurationCard } from "./components/current-configuration-card"
import { InfoCards } from "./components/info-cards"
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"
import { toast } from "@/lib/toast"
import CorruptionTestComponent from "@/components/corruption-test-component"

export default function Settings() {
  const {
    // State
    captureInterval,
    setCaptureInterval,
    timezone,
    setTimezone,
    generateThumbnails,
    setGenerateThumbnails,
    imageCaptureType,
    setImageCaptureType,
    openWeatherApiKey,
    setOpenWeatherApiKey,
    apiKeyModified,
    setApiKeyModified,
    originalApiKeyHash,
    weatherEnabled,
    setWeatherEnabled,
    sunriseSunsetEnabled,
    setSunriseSunsetEnabled,
    latitude,
    setLatitude,
    longitude,
    setLongitude,
    logRetentionDays,
    setLogRetentionDays,
    maxLogFileSize,
    setMaxLogFileSize,
    enableDebugLogging,
    setEnableDebugLogging,
    logLevel,
    setLogLevel,
    enableLogRotation,
    setEnableLogRotation,
    enableLogCompression,
    setEnableLogCompression,
    maxLogFiles,
    setMaxLogFiles,
    corruptionDetectionEnabled,
    setCorruptionDetectionEnabled,
    corruptionScoreThreshold,
    setCorruptionScoreThreshold,
    corruptionAutoDiscardEnabled,
    setCorruptionAutoDiscardEnabled,
    corruptionAutoDisableDegraded,
    setCorruptionAutoDisableDegraded,
    corruptionDegradedConsecutiveThreshold,
    setCorruptionDegradedConsecutiveThreshold,
    corruptionDegradedTimeWindowMinutes,
    setCorruptionDegradedTimeWindowMinutes,
    corruptionDegradedFailurePercentage,
    setCorruptionDegradedFailurePercentage,
    corruptionHeavyDetectionEnabled,
    setCorruptionHeavyDetectionEnabled,

    loading,
    saving,

    // Actions
    saveSettings,
  } = useSettings()

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault()
    await saveSettings()
  }

  // TODO: This needs to be moved to a layout file
  if (loading) {
    return (
      <div className='flex items-center justify-center min-h-[60vh]'>
        <div className='space-y-6 text-center'>
          <div className='relative'>
            <div className='w-16 h-16 mx-auto border-4 rounded-full border-cyan/20 border-t-cyan animate-spin' />
            <div
              className='absolute inset-0 w-16 h-16 mx-auto border-4 rounded-full border-purple/20 border-b-purple-light animate-spin'
              style={{
                animationDirection: "reverse",
                animationDuration: "1.5s",
              }}
            />
            <div
              className='absolute w-12 h-12 mx-auto border-2 rounded-full inset-2 border-pink/30 border-l-pink animate-spin'
              style={{ animationDuration: "2s" }}
            />
          </div>
          <div>
            <p className='font-medium text-white'>Loading settings...</p>
            <p className='mt-1 text-sm text-grey-light/60'>
              Configuring system preferences
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className='max-w-4xl mx-auto space-y-8'>
      {/* Header */}
      <div className='space-y-4'>
        <div>
          <h1 className='text-4xl font-bold gradient-text'>Settings</h1>
          <p className='mt-2 text-muted-foreground'>
            Configure capture intervals and system preferences
          </p>
        </div>
      </div>

      {/* Unified Settings Form */}
      <form onSubmit={handleSaveSettings} className='space-y-6'>
        {/* Capture Settings*/}
        <CaptureSettingsCard
          captureInterval={captureInterval}
          setCaptureInterval={setCaptureInterval}
          generateThumbnails={generateThumbnails}
          setGenerateThumbnails={setGenerateThumbnails}
          imageCaptureType={imageCaptureType}
          setImageCaptureType={setImageCaptureType}
          saving={saving}
        />

        {/* Timezone Settings - Full Width */}
        <TimezoneSettingsCard
          timezone={timezone}
          saving={saving}
          onTimezoneChange={setTimezone}
        />

        {/* Weather Settings - Full Width */}
        <WeatherSettingsCard
          weatherEnabled={weatherEnabled}
          setWeatherEnabled={setWeatherEnabled}
          sunriseSunsetEnabled={sunriseSunsetEnabled}
          setSunriseSunsetEnabled={setSunriseSunsetEnabled}
          latitude={latitude}
          setLatitude={setLatitude}
          longitude={longitude}
          setLongitude={setLongitude}
          openWeatherApiKey={openWeatherApiKey}
          apiKeyModified={apiKeyModified}
          originalApiKeyHash={originalApiKeyHash}
        />

        {/* Additional Settings Grid */}
        <div className='grid gap-6 lg:grid-cols-2'>
          {/* External Services */}
          <ApiKeySettingsCard
            openWeatherApiKey={openWeatherApiKey}
            setOpenWeatherApiKey={setOpenWeatherApiKey}
            apiKeyModified={apiKeyModified}
            setApiKeyModified={setApiKeyModified}
            originalApiKeyHash={originalApiKeyHash}
          />

          {/* System Maintenance */}
          <LoggingSettingsCard
            logRetentionDays={logRetentionDays}
            setLogRetentionDays={setLogRetentionDays}
            maxLogFileSize={maxLogFileSize}
            setMaxLogFileSize={setMaxLogFileSize}
            enableDebugLogging={enableDebugLogging}
            setEnableDebugLogging={setEnableDebugLogging}
            logLevel={logLevel}
            setLogLevel={setLogLevel}
            enableLogRotation={enableLogRotation}
            setEnableLogRotation={setEnableLogRotation}
            enableLogCompression={enableLogCompression}
            setEnableLogCompression={setEnableLogCompression}
            maxLogFiles={maxLogFiles}
            setMaxLogFiles={setMaxLogFiles}
          />
        </div>

        {/* Corruption Detection Settings - Full Width */}
        <CorruptionSettingsCard
          corruptionDetectionEnabled={corruptionDetectionEnabled}
          setCorruptionDetectionEnabled={setCorruptionDetectionEnabled}
          corruptionScoreThreshold={corruptionScoreThreshold}
          setCorruptionScoreThreshold={setCorruptionScoreThreshold}
          corruptionAutoDiscardEnabled={corruptionAutoDiscardEnabled}
          setCorruptionAutoDiscardEnabled={setCorruptionAutoDiscardEnabled}
          corruptionAutoDisableDegraded={corruptionAutoDisableDegraded}
          setCorruptionAutoDisableDegraded={setCorruptionAutoDisableDegraded}
          corruptionDegradedConsecutiveThreshold={
            corruptionDegradedConsecutiveThreshold
          }
          setCorruptionDegradedConsecutiveThreshold={
            setCorruptionDegradedConsecutiveThreshold
          }
          corruptionDegradedTimeWindowMinutes={
            corruptionDegradedTimeWindowMinutes
          }
          setCorruptionDegradedTimeWindowMinutes={
            setCorruptionDegradedTimeWindowMinutes
          }
          corruptionDegradedFailurePercentage={
            corruptionDegradedFailurePercentage
          }
          setCorruptionDegradedFailurePercentage={
            setCorruptionDegradedFailurePercentage
          }
          corruptionHeavyDetectionEnabled={corruptionHeavyDetectionEnabled}
          setCorruptionHeavyDetectionEnabled={
            setCorruptionHeavyDetectionEnabled
          }
        />
        <CorruptionTestComponent />
        {/*  Save Button */}
        <div className='flex justify-center pt-4 pb-2'>
          <Button
            type='submit'
            disabled={saving}
            className='transition-colors duration-300 ease-in text-black min-w-[200px] bg-primary hover:bg-primary/80 font-medium'
          >
            {saving ? (
              <>
                <RefreshCw className='w-4 h-4 mr-2 animate-spin' />
                Saving Settings...
              </>
            ) : (
              <>
                <Save className='w-4 h-4 mr-2' />
                Save All Settings
              </>
            )}
          </Button>
        </div>

        {/* Danger Zone - Full Width */}
        <DangerZoneCard />
      </form>

      {/* Current Configuration - Full Width */}
      <CurrentConfigurationCard
        settings={{
          captureInterval,
          timezone,
          openWeatherApiKey,
          generateThumbnails,
          imageCaptureType,
          logLevel,
        }}
      />

      {/* Info Cards */}
      <InfoCards />
    </div>
  )
}
